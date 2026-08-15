from collections.abc import Callable
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from services.api.app.application.errors import ResourceConflict
from services.api.app.infrastructure.creative_repositories import _add as creative_add
from services.api.app.infrastructure.review_revision_repositories import _flush as review_flush
from services.api.app.infrastructure.visual_planning_repositories import _flush as visual_flush


@pytest.fixture
def helper_cases() -> list[tuple[str, Callable[..., object]]]:
    return [
        ("creative", creative_add),
        ("visual_planning", visual_flush),
        ("review_revision", review_flush),
    ]


def _call_helper(helper: Callable[..., object], session: Mock) -> object:
    if helper is creative_add:
        return helper(session, object(), object())
    return helper(session, object())


@pytest.mark.parametrize(
    "db_error",
    [
        IntegrityError("insert", {}, RuntimeError("integrity detail")),
    ],
)
def test_all_flush_helpers_map_integrity_errors_to_resource_conflict(
    helper_cases: list[tuple[str, Callable[..., object]]], db_error: IntegrityError
) -> None:
    for _, helper in helper_cases:
        session = Mock()
        session.flush.side_effect = db_error

        with pytest.raises(ResourceConflict):
            _call_helper(helper, session)


@pytest.mark.parametrize(
    "db_error",
    [
        OperationalError("insert", {}, RuntimeError("operational detail")),
        ProgrammingError("insert", {}, RuntimeError("programming detail")),
    ],
)
def test_all_flush_helpers_propagate_non_integrity_errors(
    helper_cases: list[tuple[str, Callable[..., object]]], db_error: Exception
) -> None:
    for _, helper in helper_cases:
        session = Mock()
        session.flush.side_effect = db_error

        with pytest.raises(type(db_error)) as raised:
            _call_helper(helper, session)
        assert raised.value is db_error
