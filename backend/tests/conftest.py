import pytest
from fastapi.testclient import TestClient

from resumefit.app import create_app
from resumefit.config import AppConfig
from resumefit.db import Database


@pytest.fixture
def config(tmp_path):
    return AppConfig.for_root(tmp_path)


@pytest.fixture
def db(config):
    database = Database(config)
    database.initialize()
    return database


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path))
