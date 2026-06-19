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
