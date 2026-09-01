"""Local content store and serial SQLite receipt ledger.

The ledger uses one SQLite transaction per opening or append.  It is a local,
single-writer profile; it does not claim distributed authority conservation or
general crash safety beyond SQLite's documented transaction boundary.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from .accounting import AccountHeader, OpeningBundle, TypedReceipt, VersionOpening
from .canonical import (
    CanonicalJSONError,
    canonical_bytes,
    load_bytes_strict,
    raw_sha256,
    sha256_id,
)
from .models import HashRef

_HASH_REF = TypeAdapter(HashRef)


class LedgerError(RuntimeError):
    """Raised when an append would rewrite, fork, or corrupt the serial ledger."""


class SQLiteLedger:
    """A content-addressed, append-only, serial ledger backed by SQLite."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, isolation_level=None, timeout=5)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA journal_mode = DELETE")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS objects (
                    object_ref TEXT PRIMARY KEY,
                    canonical_bytes BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK (version >= 1),
                    header_ref TEXT NOT NULL UNIQUE,
                    header_bytes BLOB NOT NULL,
                    PRIMARY KEY (account_id, version)
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    admission_order INTEGER NOT NULL CHECK (admission_order >= 0),
                    receipt_bytes BLOB NOT NULL,
                    UNIQUE (account_id, admission_order)
                );
                CREATE TABLE IF NOT EXISTS serial_tokens (
                    token_ref TEXT PRIMARY KEY,
                    consumed_by TEXT
                );
                """
            )

    @staticmethod
    def _insert_exact(
        connection: sqlite3.Connection,
        table: str,
        key_column: str,
        key: str,
        bytes_column: str,
        data: bytes,
        insert_sql: str,
        insert_values: tuple[object, ...],
    ) -> bool:
        existing = connection.execute(
            f"SELECT {bytes_column} FROM {table} WHERE {key_column} = ?", (key,)
        ).fetchone()
        if existing is not None:
            if bytes(existing[0]) != data:
                raise LedgerError(f"refused non-identical rewrite of {key}")
            return False
        connection.execute(insert_sql, insert_values)
        return True

    def put_object(self, value: object) -> str:
        data = canonical_bytes(value)
        object_ref = raw_sha256(data)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._insert_exact(
                    connection,
                    "objects",
                    "object_ref",
                    object_ref,
                    "canonical_bytes",
                    data,
                    "INSERT INTO objects(object_ref, canonical_bytes) VALUES (?, ?)",
                    (object_ref, data),
                )
            except Exception:
                connection.execute("ROLLBACK")
                raise
            else:
                connection.execute("COMMIT")
        return object_ref

    def get_object(self, object_ref: str) -> bytes:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT canonical_bytes FROM objects WHERE object_ref = ?",
                (object_ref,),
            ).fetchone()
        if row is None:
            raise KeyError(object_ref)
        data = bytes(row[0])
        if raw_sha256(data) != object_ref:
            raise LedgerError(f"stored object digest mismatch: {object_ref}")
        load_bytes_strict(data, require_canonical=True)
        return data

    @staticmethod
    def _insert_account(connection: sqlite3.Connection, account: AccountHeader) -> bool:
        data = canonical_bytes(account)
        header_ref = sha256_id(account)
        existing = connection.execute(
            "SELECT header_bytes FROM accounts WHERE account_id = ? AND version = ?",
            (account.account_id, account.version),
        ).fetchone()
        if existing is not None:
            if bytes(existing[0]) != data:
                raise LedgerError("refused account-version rewrite")
            return False
        connection.execute(
            """
            INSERT INTO accounts(account_id, version, header_ref, header_bytes)
            VALUES (?, ?, ?, ?)
            """,
            (account.account_id, account.version, header_ref, data),
        )
        return True

    @staticmethod
    def _insert_receipt(connection: sqlite3.Connection, receipt: TypedReceipt) -> bool:
        if not isinstance(
            receipt.header.account_ref, str
        ) or not receipt.header.account_ref.startswith("sha256:"):
            raise LedgerError(
                "package-level receipts are not admitted by account append"
            )
        data = canonical_bytes(receipt)
        existing = connection.execute(
            "SELECT receipt_bytes FROM receipts WHERE receipt_id = ?",
            (receipt.header.receipt_id,),
        ).fetchone()
        if existing is not None:
            if bytes(existing[0]) != data:
                raise LedgerError("refused receipt identity rewrite")
            return False
        previous = connection.execute(
            "SELECT MAX(admission_order) FROM receipts WHERE account_id = ?",
            (receipt.header.account_ref,),
        ).fetchone()
        prior_order = None if previous is None else previous[0]
        expected_order = 0 if prior_order is None else int(prior_order) + 1
        if receipt.header.admission_order != expected_order:
            raise LedgerError(
                "receipt admission order conflicts with the next serial account order"
            )
        connection.execute(
            """
            INSERT INTO receipts(receipt_id, account_id, admission_order, receipt_bytes)
            VALUES (?, ?, ?, ?)
            """,
            (
                receipt.header.receipt_id,
                receipt.header.account_ref,
                receipt.header.admission_order,
                data,
            ),
        )
        return True

    def commit_opening(self, bundle: OpeningBundle) -> None:
        """Atomically admit a new account header and its own CutReceipt."""

        try:
            bundle = OpeningBundle.model_validate(bundle)
        except ValidationError as exc:
            raise LedgerError("invalid or rewritten opening bundle") from exc
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._insert_account(connection, bundle.account)
                self._insert_receipt(connection, bundle.cut_receipt)
            except sqlite3.IntegrityError as exc:
                connection.execute("ROLLBACK")
                raise LedgerError("opening conflicts with append-only ledger") from exc
            except Exception:
                connection.execute("ROLLBACK")
                raise
            else:
                connection.execute("COMMIT")

    def commit_version(self, opening: VersionOpening) -> None:
        """Atomically admit one exact next account version and transition receipt."""

        try:
            opening = VersionOpening.model_validate(opening)
        except ValidationError as exc:
            raise LedgerError("invalid or rewritten version opening") from exc
        prior_version = opening.account.version - 1
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                prior = connection.execute(
                    """
                    SELECT header_ref FROM accounts
                    WHERE account_id = ? AND version = ?
                    """,
                    (opening.account.account_id, prior_version),
                ).fetchone()
                if prior is None:
                    raise LedgerError("immediate prior account version is absent")
                if str(prior[0]) != opening.account.immediate_prior_version_ref:
                    raise LedgerError("VERSION continuity reference mismatch")
                self._insert_account(connection, opening.account)
                self._insert_receipt(connection, opening.transition_receipt)
            except sqlite3.IntegrityError as exc:
                connection.execute("ROLLBACK")
                raise LedgerError("version conflicts with append-only ledger") from exc
            except Exception:
                connection.execute("ROLLBACK")
                raise
            else:
                connection.execute("COMMIT")

    def append_receipt(self, account: AccountHeader, receipt: TypedReceipt) -> None:
        try:
            account = AccountHeader.model_validate(account)
            receipt = TypedReceipt.model_validate(receipt)
        except ValidationError as exc:
            raise LedgerError("invalid or rewritten receipt append") from exc
        if receipt.header.account_ref != account.account_id:
            raise LedgerError("receipt account binding mismatch")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT header_ref FROM accounts
                    WHERE account_id = ? AND version = ?
                    """,
                    (account.account_id, account.version),
                ).fetchone()
                if row is None or str(row[0]) != sha256_id(account):
                    raise LedgerError("exact account version is not present")
                self._insert_receipt(connection, receipt)
            except sqlite3.IntegrityError as exc:
                connection.execute("ROLLBACK")
                raise LedgerError("receipt conflicts with append-only ledger") from exc
            except Exception:
                connection.execute("ROLLBACK")
                raise
            else:
                connection.execute("COMMIT")

    def register_token(self, token_ref: str) -> None:
        try:
            token_ref = _HASH_REF.validate_python(token_ref)
        except ValidationError as exc:
            raise LedgerError("serial token is not a canonical hash reference") from exc
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO serial_tokens(token_ref, consumed_by)
                VALUES (?, NULL)
                """,
                (token_ref,),
            )

    def consume_token(self, token_ref: str, decision_ref: str) -> bool:
        """Consume once; exact replay returns False, a competing use is refused."""

        try:
            token_ref = _HASH_REF.validate_python(token_ref)
            decision_ref = _HASH_REF.validate_python(decision_ref)
        except ValidationError as exc:
            raise LedgerError(
                "token and decision must be canonical hash references"
            ) from exc
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT consumed_by FROM serial_tokens WHERE token_ref = ?",
                    (token_ref,),
                ).fetchone()
                if row is None:
                    raise LedgerError("serial token was not registered")
                consumed_by = row[0]
                if consumed_by is None:
                    connection.execute(
                        "UPDATE serial_tokens SET consumed_by = ? WHERE token_ref = ?",
                        (decision_ref, token_ref),
                    )
                    first_use = True
                elif str(consumed_by) == decision_ref:
                    first_use = False
                else:
                    raise LedgerError(
                        "serial token already consumed by another decision"
                    )
            except Exception:
                connection.execute("ROLLBACK")
                raise
            else:
                connection.execute("COMMIT")
        return first_use

    def counts(self) -> dict[str, int]:
        with self._connect() as connection:
            return {
                table: int(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
                for table in ("objects", "accounts", "receipts", "serial_tokens")
            }

    def verify(self) -> list[str]:
        """Return integrity errors without mutating the ledger."""

        errors: list[str] = []
        with self._connect() as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                errors.append(f"sqlite_integrity:{integrity}")
            for object_ref, data in connection.execute(
                "SELECT object_ref, canonical_bytes FROM objects"
            ):
                try:
                    exact = bytes(data)
                    load_bytes_strict(exact, require_canonical=True)
                    if raw_sha256(exact) != object_ref:
                        errors.append(f"object_hash:{object_ref}")
                except (CanonicalJSONError, ValueError) as exc:
                    errors.append(f"object_parse:{object_ref}:{type(exc).__name__}")
            for account_id, version, header_ref, data in connection.execute(
                "SELECT account_id, version, header_ref, header_bytes FROM accounts"
            ):
                try:
                    value = load_bytes_strict(bytes(data), require_canonical=True)
                    account = AccountHeader.model_validate(value)
                    if account.account_id != account_id or account.version != version:
                        errors.append(f"account_binding:{account_id}:{version}")
                    if sha256_id(account) != header_ref:
                        errors.append(f"account_hash:{account_id}:{version}")
                except (CanonicalJSONError, ValidationError, ValueError) as exc:
                    errors.append(
                        f"account_parse:{account_id}:{version}:{type(exc).__name__}"
                    )
            for receipt_id, account_id, order, data in connection.execute(
                """
                SELECT receipt_id, account_id, admission_order, receipt_bytes
                FROM receipts
                """
            ):
                try:
                    value = load_bytes_strict(bytes(data), require_canonical=True)
                    receipt = TypedReceipt.model_validate(value)
                    if (
                        receipt.header.receipt_id != receipt_id
                        or receipt.header.account_ref != account_id
                        or receipt.header.admission_order != order
                    ):
                        errors.append(f"receipt_binding:{receipt_id}")
                except (CanonicalJSONError, ValidationError, ValueError) as exc:
                    errors.append(f"receipt_parse:{receipt_id}:{type(exc).__name__}")
            for token_ref, consumed_by in connection.execute(
                "SELECT token_ref, consumed_by FROM serial_tokens"
            ):
                try:
                    _HASH_REF.validate_python(token_ref)
                    if consumed_by is not None:
                        _HASH_REF.validate_python(consumed_by)
                except ValidationError as exc:
                    errors.append(f"token_parse:{token_ref}:{type(exc).__name__}")
        return errors


__all__ = ["LedgerError", "SQLiteLedger"]
