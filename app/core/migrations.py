"""Mise à jour du schéma de la base au démarrage de l'API, avec Alembic."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
# Révision qui décrit les tables créées par create_all avant l'arrivée d'Alembic
BASELINE_REVISION = "8de2cf1f0969"


def run_migrations(engine: Engine) -> None:
    """Applique les migrations en attente.

    Une base créée avant Alembic (tables présentes, pas de table `alembic_version`)
    est d'abord marquée comme étant à la révision initiale : ses tables ne sont
    pas recréées et aucune donnée n'est perdue.
    """
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["configure_logger"] = False  # garder la configuration de logs de l'API

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())

        if "alembic_version" not in tables and "users" in tables:
            logger.info("Base existante sans historique de migration : marquée à la révision %s", BASELINE_REVISION)
            command.stamp(config, BASELINE_REVISION)

        command.upgrade(config, "head")
