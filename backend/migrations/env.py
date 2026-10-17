from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

import moneytalk.models  # noqa: F401  registra todos los modelos
from moneytalk.config import get_settings
from moneytalk.models.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    # Permite que los tests apunten a otra BD con `-x url=...`.
    return context.get_x_argument(as_dictionary=True).get("url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection") or create_engine(_url())
    if hasattr(connectable, "connect"):
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    else:
        context.configure(connection=connectable, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
