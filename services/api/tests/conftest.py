from collections.abc import Callable, Iterator

import pytest
from sqlalchemy import Engine, create_engine, text

from infra.scripts.reset_test_database import require_test_database_url
from services.api.app.application.services import TenantApplicationService
from services.api.app.config import LOCAL_DATABASE_URL
from services.api.app.infrastructure.database import SessionFactory, create_session_factory
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork

DEFAULT_TEST_DATABASE_URL = LOCAL_DATABASE_URL.replace("foundation_local", "foundation_test")


def _require_test_database(url: str) -> str:
    return require_test_database_url(url)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    import os

    return _require_test_database(os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL))


@pytest.fixture(scope="session")
def database_engine(test_database_url: str) -> Iterator[Engine]:
    engine = create_engine(test_database_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def clean_database(database_engine: Engine) -> Iterator[None]:
    _truncate(database_engine)
    yield
    _truncate(database_engine)


@pytest.fixture(scope="session")
def persistence_session_factory(database_engine: Engine) -> SessionFactory:
    return create_session_factory(database_engine)


@pytest.fixture
def uow_factory(
    persistence_session_factory: SessionFactory, clean_database: None
) -> Callable[[], SqlAlchemyUnitOfWork]:
    del clean_database
    return lambda: SqlAlchemyUnitOfWork(persistence_session_factory)


@pytest.fixture
def persistence_service(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
) -> TenantApplicationService:
    return TenantApplicationService(uow_factory)


def _truncate(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE requirement_issues, brief_versions, briefs, audit_events, "
                "projects, memberships, workspaces, organizations CASCADE"
            )
        )
