from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_column_if_missing(table_name: str, column_name: str, ddl: str) -> None:
    inspector = inspect(engine)

    try:
        existing_columns = [column["name"] for column in inspector.get_columns(table_name)]
    except Exception:
        return

    if column_name in existing_columns:
        return

    with engine.begin() as conn:
        conn.execute(text(ddl))


def _ensure_schema_updates() -> None:
    dialect = engine.dialect.name

    if dialect == "postgresql":
        _add_column_if_missing(
            "interno_funcionarios",
            "acessos",
            "ALTER TABLE interno_funcionarios ADD COLUMN acessos JSONB",
        )
    else:
        _add_column_if_missing(
            "interno_funcionarios",
            "acessos",
            "ALTER TABLE interno_funcionarios ADD COLUMN acessos TEXT",
        )


def init_db() -> None:
    # Importa models antes do create_all para registrar as tabelas no metadata.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_schema_updates()
