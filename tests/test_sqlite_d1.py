from __future__ import annotations

import asyncio
import sqlite3
import unittest

from api.sqlite_d1 import SqliteD1Database


class SqliteD1Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = SqliteD1Database.open(":memory:")
        await self.database.prepare(
            "CREATE TABLE learners (learner_id TEXT PRIMARY KEY, display_name TEXT NOT NULL)"
        ).run()

    async def asyncTearDown(self) -> None:
        await self.database.close()

    async def test_first_supports_scalar_and_row_results(self) -> None:
        await self.database.prepare(
            "INSERT INTO learners (learner_id, display_name) VALUES (?, ?)"
        ).bind("learner-1", "Ada").run()

        name = await self.database.prepare(
            "SELECT display_name FROM learners WHERE learner_id = ?"
        ).bind("learner-1").first("display_name")
        row = await self.database.prepare(
            "SELECT learner_id, display_name FROM learners WHERE learner_id = ?"
        ).bind("learner-1").first()

        self.assertEqual(name, "Ada")
        self.assertEqual(row, {"learner_id": "learner-1", "display_name": "Ada"})

    async def test_all_returns_the_result_shape_used_by_runtime_glue(self) -> None:
        await self.database.prepare(
            "INSERT INTO learners (learner_id, display_name) VALUES (?, ?)"
        ).bind("learner-1", "Ada").run()

        result = await self.database.prepare(
            "SELECT learner_id, display_name FROM learners ORDER BY learner_id"
        ).all()

        self.assertIs(result["success"], True)
        self.assertEqual(
            result["results"],
            [{"learner_id": "learner-1", "display_name": "Ada"}],
        )

    async def test_batch_commits_all_statements_and_returns_each_result(self) -> None:
        result = await self.database.batch(
            [
                self.database.prepare(
                    "INSERT INTO learners (learner_id, display_name) VALUES (?, ?)"
                ).bind("learner-1", "Ada"),
                self.database.prepare(
                    "SELECT display_name FROM learners WHERE learner_id = ?"
                ).bind("learner-1"),
            ]
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]["results"], [{"display_name": "Ada"}])

    async def test_batch_rolls_back_every_statement_after_a_failure(self) -> None:
        await self.database.prepare(
            "INSERT INTO learners (learner_id, display_name) VALUES (?, ?)"
        ).bind("existing", "Existing").run()

        with self.assertRaises(sqlite3.IntegrityError):
            await self.database.batch(
                [
                    self.database.prepare(
                        "INSERT INTO learners (learner_id, display_name) VALUES (?, ?)"
                    ).bind("should-rollback", "Temporary"),
                    self.database.prepare(
                        "INSERT INTO learners (learner_id, display_name) VALUES (?, ?)"
                    ).bind("existing", "Duplicate"),
                ]
            )

        count = await self.database.prepare(
            "SELECT COUNT(*) AS learner_count FROM learners WHERE learner_id = ?"
        ).bind("should-rollback").first("learner_count")
        self.assertEqual(count, 0)


class SqliteD1MultiLoopTests(unittest.TestCase):
    def test_one_database_can_serve_sequential_http_event_loops(self) -> None:
        database = SqliteD1Database.open(":memory:")
        asyncio.run(database.prepare("CREATE TABLE values_table (value INTEGER)").run())
        asyncio.run(database.prepare("INSERT INTO values_table VALUES (?)").bind(7).run())
        value = asyncio.run(
            database.prepare("SELECT value FROM values_table").first("value")
        )
        asyncio.run(database.close())

        self.assertEqual(value, 7)


if __name__ == "__main__":
    unittest.main()
