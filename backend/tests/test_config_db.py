from resumefit.config import AppConfig
from resumefit.db import Database


def test_data_root_layout_creates_all_local_directories(tmp_path):
    config = AppConfig.for_root(tmp_path)

    assert config.imports_dir.is_dir()
    assert config.images_dir.is_dir()
    assert config.exports_dir.is_dir()
    assert config.backups_dir.is_dir()
    assert config.logs_dir.is_dir()
    assert config.database_path.parent == tmp_path


def test_database_initialization_creates_workspace_and_fts_tables(tmp_path):
    config = AppConfig.for_root(tmp_path)
    db = Database(config)
    db.initialize()

    assert db.fetchone("SELECT id FROM workspaces WHERE slug = 'local'")["id"]
    assert (
        db.fetchone("SELECT name FROM sqlite_master WHERE name = 'fact_search'")["name"]
        == "fact_search"
    )


def test_initialization_is_idempotent_and_records_schema_version(tmp_path):
    config = AppConfig.for_root(tmp_path)

    Database(config).initialize()
    db = Database(config)
    db.initialize()

    assert db.fetchone("SELECT COUNT(*) AS n FROM workspaces")["n"] == 1
    assert db.fetchone("SELECT MAX(version) AS v FROM schema_version")["v"] >= 1


def test_foreign_keys_are_enforced(tmp_path):
    import sqlite3

    import pytest

    db = Database(AppConfig.for_root(tmp_path))
    db.initialize()

    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (id, workspace_id, name) VALUES (?, ?, ?)",
                ("p1", "missing-workspace", "智能客服"),
            )


def test_transaction_rolls_back_on_error(tmp_path):
    db = Database(AppConfig.for_root(tmp_path))
    db.initialize()
    workspace_id = db.fetchone("SELECT id FROM workspaces WHERE slug = 'local'")["id"]

    try:
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (id, workspace_id, name) VALUES (?, ?, ?)",
                ("p1", workspace_id, "智能客服"),
            )
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert db.fetchone("SELECT COUNT(*) AS n FROM projects")["n"] == 0
