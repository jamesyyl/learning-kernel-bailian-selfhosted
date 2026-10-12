"""Small SQLite adapter for the D1-shaped API used by the vNext Worker glue.

This implements only the prepared-statement methods consumed by the current
vNext Runtime. It does not emulate Cloudflare D1 limits, edge consistency, or
deployment behavior.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SqlValue = object


@dataclass(frozen=True, slots=True)
class SqliteD1PreparedStatement:
    """One SQL statement and its bound parameters."""

    database: SqliteD1Database
    query: str
    values: tuple[_SqlValue, ...] = ()

    def bind(self, *values: _SqlValue) -> SqliteD1PreparedStatement:
        return SqliteD1PreparedStatement(self.database, self.query, tuple(values))

    async def first(self, column_name: str | None = None) -> object | None:
        async with self.database._lock:
            return self._first_sync(column_name)

    async def all(self) -> dict[str, object]:
        async with self.database._lock:
            return self._execute_sync()

    async def run(self) -> dict[str, object]:
        async with self.database._lock:
            return self._execute_sync()

    def _first_sync(self, column_name: str | None) -> object | None:
        result = self._execute_sync()
        rows = result["results"]
        assert isinstance(rows, list)
        if not rows:
            return None
        row = rows[0]
        assert isinstance(row, dict)
        if column_name is None:
            return row
        return row.get(column_name)

    def _execute_sync(self) -> dict[str, object]:
        connection = self.database._connection
        changes_before = connection.total_changes
        cursor = connection.execute(self.query, self.values)
        rows = (
            [dict(row) for row in cursor.fetchall()]
            if cursor.description is not None
            else []
        )
        return {
            "success": True,
            "results": rows,
            "meta": {
                "changes": max(0, connection.total_changes - changes_before),
                "last_row_id": cursor.lastrowid,
            },
        }


class SqliteD1Database:
    """Serialize SQLite access and expose the D1 methods the Worker glue uses."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._lock = asyncio.Lock()

    @classmethod
    def open(cls, path: str | Path) -> SqliteD1Database:
        connection = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        connection.execute("PRAGMA journal_mode = WAL")
        return cls(connection)

    def prepare(self, query: str) -> SqliteD1PreparedStatement:
        if not query.strip():
            raise ValueError("SQL query must not be empty.")
        return SqliteD1PreparedStatement(self, query)

    async def batch(
        self,
        statements: Sequence[SqliteD1PreparedStatement],
    ) -> list[dict[str, object]]:
        if any(statement.database is not self for statement in statements):
            raise ValueError("A SQLite batch cannot mix database connections.")
        async with self._lock:
            return self._batch_sync(statements)

    def _batch_sync(
        self,
        statements: Sequence[SqliteD1PreparedStatement],
    ) -> list[dict[str, object]]:
        connection = self._connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            results = [statement._execute_sync() for statement in statements]
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        return results

    async def close(self) -> None:
        async with self._lock:
            self._connection.close()


__all__ = ["SqliteD1Database", "SqliteD1PreparedStatement"]
