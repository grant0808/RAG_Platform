import pytest

from foundry.core.errors import ValidationError
from foundry.services.tables import TableStore


def test_safe_table_store_rejects_writes(tmp_path):
    store = TableStore(tmp_path / "tables.duckdb")
    try:
        with pytest.raises(ValidationError, match="Only one SELECT|forbidden"):
            store.execute_safe("DROP TABLE anything")
    finally:
        store.close()


def test_safe_table_store_limits_results(tmp_path):
    store = TableStore(tmp_path / "tables.duckdb")
    try:
        store.connection.execute("CREATE TABLE metrics(value INTEGER)")
        store.connection.execute("INSERT INTO metrics SELECT * FROM range(0, 10)")
        result = store.execute_safe("SELECT value FROM metrics ORDER BY value", max_rows=3)
        assert result["rows"] == [[0], [1], [2]]
    finally:
        store.close()


def test_safe_table_store_enforces_table_allowlist(tmp_path):
    store = TableStore(tmp_path / "tables.duckdb")
    try:
        store.connection.execute("CREATE TABLE allowed(value INTEGER)")
        store.connection.execute("CREATE TABLE private(value INTEGER)")
        result = store.execute_safe("SELECT * FROM allowed", allowed_tables={"allowed"})
        assert result["rows"] == []
        with pytest.raises(ValidationError, match="outside the allowlist"):
            store.execute_safe("SELECT * FROM private", allowed_tables={"allowed"})
    finally:
        store.close()


def test_safe_table_store_rejects_external_file_scan(tmp_path):
    store = TableStore(tmp_path / "tables.duckdb")
    try:
        with pytest.raises(ValidationError, match="outside the allowlist|forbidden"):
            store.execute_safe(
                "SELECT * FROM read_csv_auto('/etc/passwd')",
                allowed_tables={"source_table"},
            )
        with pytest.raises(ValidationError, match="forbidden"):
            store.execute_safe(
                "SELECT read_text('/etc/passwd')",
                allowed_tables={"source_table"},
            )
    finally:
        store.close()
