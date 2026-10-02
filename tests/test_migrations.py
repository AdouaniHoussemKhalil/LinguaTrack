"""Migrations Alembic : exécutées dans un processus séparé, sur des bases SQLite dédiées."""

import os
import pathlib
import sqlite3
import subprocess
import sys

import pytest

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    not os.environ["DATABASE_URL"].startswith("sqlite"), reason="tests de migration écrits pour SQLite"
)


def run(code: str, db: pathlib.Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db.as_posix()}"}
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, encoding="utf-8")


def schema(db: pathlib.Path) -> dict:
    con = sqlite3.connect(db)
    tables = [t for (t,) in con.execute("select name from sqlite_master where type='table' and name != 'alembic_version' order by name")]
    # Colonnes triées : une migration ajoute une colonne en fin de table, create_all à sa place dans le modèle
    result = {t: sorted((c[1], c[2], c[3]) for c in con.execute(f"pragma table_info({t})")) for t in tables}
    con.close()
    return result


START_API = "from fastapi.testclient import TestClient\nfrom app.main import app\nwith TestClient(app): pass"
CREATE_ALL = "from app.core.database import Base, engine\nimport app.models\nBase.metadata.create_all(bind=engine)"


def test_empty_database_gets_full_schema(tmp_path):
    migrated, reference = tmp_path / "migrated.db", tmp_path / "reference.db"
    assert run(START_API, migrated).returncode == 0
    assert run(CREATE_ALL, reference).returncode == 0
    assert schema(migrated) == schema(reference)  # migrations == modèles


def test_database_created_before_alembic_keeps_its_data(tmp_path):
    db = tmp_path / "legacy.db"
    # Ancien fonctionnement : create_all sur le schéma initial (sans les colonnes ajoutées depuis)
    legacy = (
        "import sqlalchemy as sa\nfrom app.core.database import Base, engine\nimport app.models\n"
        "from app.models.text import TextSubmission\n"
        "Base.metadata.create_all(bind=engine)\n"
        "with engine.begin() as c: c.execute(sa.text('ALTER TABLE texts DROP COLUMN feedback'))\n"
        # Avant le service d'authentification : mot de passe local, pas de auth_user_id
        "with engine.begin() as c: c.execute(sa.text('DROP INDEX ix_users_auth_user_id'))\n"
        "with engine.begin() as c: c.execute(sa.text('ALTER TABLE users DROP COLUMN auth_user_id'))\n"
        "with engine.begin() as c: c.execute(sa.text(\"ALTER TABLE users ADD COLUMN password VARCHAR NOT NULL DEFAULT ''\"))\n"
        "with engine.begin() as c: c.execute(sa.text(\"INSERT INTO users (id, email, password, first_name, last_name, level) "
        "VALUES ('0123456789abcdef0123456789abcdef', 'ancien@exemple.com', 'h', 'A', 'B', 'B2')\"))"
    )
    result = run(legacy, db)
    assert result.returncode == 0, result.stderr
    assert run(START_API, db).returncode == 0

    con = sqlite3.connect(db)
    assert con.execute("select email, level from users").fetchall() == [("ancien@exemple.com", "B2")]
    assert "feedback" in [c[1] for c in con.execute("pragma table_info(texts)")]  # migration appliquée
    columns = [c[1] for c in con.execute("pragma table_info(users)")]
    assert "auth_user_id" in columns and "password" not in columns
    con.close()


def test_models_and_migrations_are_aligned(tmp_path):
    db = tmp_path / "check.db"
    assert run(START_API, db).returncode == 0
    result = subprocess.run([sys.executable, "-m", "alembic", "check"], cwd=BACKEND_DIR, capture_output=True, text=True,
                            env={**os.environ, "DATABASE_URL": f"sqlite:///{db.as_posix()}"})
    assert "No new upgrade operations detected" in result.stdout + result.stderr
