"""Fixtures de pruebas.

Las pruebas corren contra Postgres real (no SQLite): usamos JSONB, regex en CHECKs y
NUMERIC, que SQLite no respeta igual. Las migraciones se aplican una vez por sesión y
cada prueba corre dentro de una transacción que se revierte al final.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.orm import Session

from moneytalk.db import get_db
from moneytalk.main import app

BACKEND_DIR = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://moneytalk:devlocal@127.0.0.1:5433/moneytalk_test",
)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = create_engine(TEST_DATABASE_URL)
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    with eng.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    conn = engine.connect()
    trans = conn.begin()
    yield conn
    trans.rollback()
    conn.close()


@pytest.fixture
def db(connection: Connection) -> Iterator[Session]:
    # Los commit() del código bajo prueba se vuelven SAVEPOINTs: el rollback final los borra.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
