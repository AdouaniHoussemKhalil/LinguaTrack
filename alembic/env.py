"""Environnement Alembic : URL et modèles repris de l'application."""

from logging.config import fileConfig

from alembic import context
import sqlalchemy as sa
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.core.database import Base
import app.models  # noqa: F401  (enregistre toutes les tables dans Base.metadata)

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

# Logs Alembic seulement en ligne de commande (pas quand l'API lance les migrations)
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# SQLite ne sait pas modifier une colonne : Alembic recrée alors la table (mode batch)
RENDER_AS_BATCH = settings.DATABASE_URL.startswith("sqlite")


def compare_type(_context, _inspected_column, _metadata_column, _inspected_type, metadata_type):
    """SQLite relit les colonnes UUID comme NUMERIC : ne pas y voir un changement de type."""
    if RENDER_AS_BATCH and isinstance(metadata_type, sa.Uuid):
        return False
    return None  # comparaison par défaut d'Alembic


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=RENDER_AS_BATCH,
        compare_type=compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is None:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        with connectable.connect() as connection:
            _run(connection)
    else:
        _run(connectable)


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=RENDER_AS_BATCH,
        compare_type=compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
