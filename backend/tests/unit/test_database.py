# start backend/tests/unit/test_database.py
"""
Unit tests for database.py — covers get_db, _parse_sql_statements,
_apply_migration_file, init_db, and close_db.

Goal: 100% line coverage for src/database.py.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open


class TestGetDb:
    """Test the get_db() async generator dependency."""

    async def test_get_db_yields_session_and_closes(self):
        """Test that get_db yields a session and closes it in the finally block.

        Covers lines 44-49: the async generator body including yield and finally.
        """
        from src.database import get_db

        mock_session = AsyncMock()

        # Patch AsyncSessionLocal to return a context manager yielding mock_session
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("src.database.AsyncSessionLocal", return_value=mock_session_cm):
            # Consume the generator; it should yield exactly one session
            sessions = []
            async for session in get_db():
                sessions.append(session)

            assert len(sessions) == 1
            assert sessions[0] is mock_session
            mock_session.close.assert_awaited_once()

    async def test_get_db_closes_session_on_exception(self):
        """Test that get_db closes the session even when an exception occurs."""
        from src.database import get_db

        mock_session = AsyncMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("src.database.AsyncSessionLocal", return_value=mock_session_cm):
            gen = get_db()
            await gen.__anext__()

            # Throw an exception into the generator to trigger finally cleanup
            with pytest.raises(RuntimeError):
                await gen.athrow(RuntimeError("test error"))

            mock_session.close.assert_awaited_once()


class TestParseSqlStatements:
    """Test _parse_sql_statements() function."""

    def test_empty_sql(self):
        """Test parsing empty SQL string."""
        from src.database import _parse_sql_statements

        result = _parse_sql_statements("")
        assert result == []

    def test_single_statement(self):
        """Test parsing a single SQL statement."""
        from src.database import _parse_sql_statements

        sql = "CREATE TABLE foo (id INTEGER PRIMARY KEY);"
        result = _parse_sql_statements(sql)
        assert len(result) == 1
        assert "CREATE TABLE foo" in result[0]

    def test_multiple_statements(self):
        """Test parsing multiple SQL statements."""
        from src.database import _parse_sql_statements

        sql = "CREATE TABLE foo (id INTEGER);\nCREATE TABLE bar (id INTEGER);"
        result = _parse_sql_statements(sql)
        assert len(result) == 2

    def test_comments_and_blank_lines_skipped(self):
        """Test that comments and blank lines are skipped."""
        from src.database import _parse_sql_statements

        sql = """-- This is a comment

CREATE TABLE foo (id INTEGER);

-- Another comment
CREATE TABLE bar (id INTEGER);
"""
        result = _parse_sql_statements(sql)
        assert len(result) == 2

    def test_begin_end_block_not_split(self):
        """Test that BEGIN...END blocks are not split on semicolons."""
        from src.database import _parse_sql_statements

        sql = """CREATE TRIGGER update_timestamp
AFTER UPDATE ON tasks
BEGIN
    UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;"""
        result = _parse_sql_statements(sql)
        assert len(result) == 1
        assert "BEGIN" in result[0]
        assert "END" in result[0]

    def test_statement_without_trailing_semicolon(self):
        """Test that a trailing statement without semicolon is still captured."""
        from src.database import _parse_sql_statements

        sql = "CREATE TABLE foo (id INTEGER);\nSELECT 1"
        result = _parse_sql_statements(sql)
        assert len(result) == 2
        assert "SELECT 1" in result[1]

    def test_nested_begin_end_blocks(self):
        """Test nested BEGIN/END depth tracking."""
        from src.database import _parse_sql_statements

        sql = """CREATE TRIGGER complex_trigger
AFTER INSERT ON tasks
BEGIN
    BEGIN
        UPDATE tasks SET status = 'new';
    END;
END;"""
        result = _parse_sql_statements(sql)
        assert len(result) == 1


class TestApplyMigrationFile:
    """Test _apply_migration_file() function."""

    async def test_migration_file_not_exists(self, tmp_path):
        """Test that nonexistent migration file is a no-op."""
        from src.database import _apply_migration_file

        mock_conn = AsyncMock()
        nonexistent = tmp_path / "nonexistent.sql"

        await _apply_migration_file(mock_conn, nonexistent, "test")
        mock_conn.execute.assert_not_awaited()

    async def test_migration_file_applies_statements(self, tmp_path):
        """Test that migration file statements are executed."""
        from src.database import _apply_migration_file

        migration_file = tmp_path / "migration.sql"
        migration_file.write_text(
            "CREATE TABLE test_table (id INTEGER PRIMARY KEY);\n"
            "INSERT INTO test_table VALUES (1);"
        )

        mock_conn = AsyncMock()
        await _apply_migration_file(mock_conn, migration_file, "test migration")

        assert mock_conn.execute.await_count == 2

    async def test_migration_file_skips_empty_statements(self, tmp_path):
        """Test that empty statements in migration file are skipped."""
        from src.database import _apply_migration_file

        migration_file = tmp_path / "migration.sql"
        migration_file.write_text("CREATE TABLE test (id INTEGER);")

        mock_conn = AsyncMock()
        await _apply_migration_file(mock_conn, migration_file, "test")

        assert mock_conn.execute.await_count == 1


class TestInitDb:
    """Test init_db() function."""

    async def test_init_db_creates_tables_and_applies_migrations(self):
        """Test that init_db creates tables and applies migrations."""
        from src.database import init_db

        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_engine_cm = AsyncMock()
        mock_engine_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("src.database.engine") as mock_engine:
            mock_engine.begin.return_value = mock_engine_cm
            with patch("src.database._apply_migration_file", new_callable=AsyncMock) as mock_apply:
                await init_db()

                mock_conn.run_sync.assert_awaited_once()
                mock_apply.assert_awaited_once()

    async def test_init_db_handles_migration_exception(self):
        """Test that init_db catches and logs migration exceptions."""
        from src.database import init_db

        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock()

        mock_engine_cm = AsyncMock()
        mock_engine_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("src.database.engine") as mock_engine:
            mock_engine.begin.return_value = mock_engine_cm
            with patch(
                "src.database._apply_migration_file",
                new_callable=AsyncMock,
                side_effect=Exception("migration already applied"),
            ):
                # Should not raise; the exception is caught and logged
                await init_db()

                mock_conn.run_sync.assert_awaited_once()


class TestCloseDb:
    """Test close_db() function."""

    async def test_close_db_disposes_engine(self):
        """Test that close_db disposes the engine."""
        from src.database import close_db

        with patch("src.database.engine") as mock_engine:
            mock_engine.dispose = AsyncMock()
            await close_db()
            mock_engine.dispose.assert_awaited_once()


# end backend/tests/unit/test_database.py
