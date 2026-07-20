import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from services.api.app.application.brief_services import BriefApplicationService
from services.api.app.application.creative_services import (
    ConceptGenerationResult,
    CreativeApplicationService,
)
from services.api.app.application.errors import InvalidRequest, ResourceConflict
from services.api.app.application.model_provider import (
    DeterministicFakeProvider,
    ProviderOutcome,
    ProviderOutcomeStatus,
)
from services.api.app.domain import BriefSourceType
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork
from services.api.tests.test_brief_extraction_foundation import FIXTURES, _source

CREATIVE = Path(__file__).resolve().parents[3] / "packages" / "test-fixtures" / "creative"


def _service(session_factory: SessionFactory) -> CreativeApplicationService:
    concepts = [json.loads((CREATIVE / "valid-concept-v1.json").read_text()) for _ in range(3)]
    concepts[1]["title"] = "Second concept"
    concepts[2]["title"] = "Third concept"
    provider = DeterministicFakeProvider(
        ProviderOutcome(ProviderOutcomeStatus.SUCCESS, json.dumps({"concepts": concepts}))
    )
    return CreativeApplicationService(lambda: SqlAlchemyUnitOfWork(session_factory), provider)


def test_concept_selection_and_script_lineage(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    context, project_id, *_ = _source(persistence_session_factory, tmp_path)
    content = json.loads((FIXTURES / "valid-structured-brief-v1.json").read_text())
    brief = BriefApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    ).create_brief(
        context,
        project_id,
        title="Creative source",
        structured_content=content,
        source_type=BriefSourceType.MANUAL,
        source_reference=None,
        change_summary="Creative input",
    )
    service = _service(persistence_session_factory)
    generated = service.generate_concepts(
        context, project_id, brief.brief.id, brief.current_version.id, idempotency_key="concepts-1"
    )
    assert len(generated.candidates) == 3
    assert isinstance(service.provider, DeterministicFakeProvider)
    assert service.provider.last_request is not None
    assert service.provider.last_request.instruction_template_id == "creative_concepts_from_brief"
    assert "exactly one property named concepts" in service.provider.last_request.instructions
    assert service.provider.last_request.allow_tools is False
    replay = service.generate_concepts(
        context, project_id, brief.brief.id, brief.current_version.id, idempotency_key="concepts-1"
    )
    assert replay.replayed is True
    selected = service.select_concept(
        context,
        project_id,
        generated.run.id,
        generated.candidates[0].id,
        idempotency_key="selection-1",
    )
    with pytest.raises(ResourceConflict):
        service.select_concept(
            context,
            project_id,
            generated.run.id,
            generated.candidates[1].id,
            idempotency_key="selection-2",
        )
    service.provider = DeterministicFakeProvider(
        ProviderOutcome(
            ProviderOutcomeStatus.SUCCESS, (CREATIVE / "valid-script-v1.json").read_text()
        )
    )
    script = service.generate_script(
        context, project_id, generated.run.id, idempotency_key="script-1"
    )
    assert isinstance(service.provider, DeterministicFakeProvider)
    assert service.provider.last_request is not None
    assert service.provider.last_request.instruction_template_id == "script_from_selected_concept"
    assert "target_duration_seconds must equal" in service.provider.last_request.instructions
    assert service.provider.last_request.allow_tools is False
    assert script.version.concept_selection_id == selected.selection.id
    assert script.version.brief_version_id == brief.current_version.id
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM creative_concept_candidates")) == 3
        assert connection.scalar(text("SELECT count(*) FROM creative_concept_selections")) == 1
        assert connection.scalar(text("SELECT count(*) FROM script_versions")) == 1


def test_concept_wrong_count_rolls_back_operation(
    persistence_session_factory: SessionFactory, clean_database: None, tmp_path: Path
) -> None:
    del clean_database
    context, project_id, *_ = _source(persistence_session_factory, tmp_path)
    content = json.loads((FIXTURES / "valid-structured-brief-v1.json").read_text())
    brief = BriefApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    ).create_brief(
        context,
        project_id,
        title="Creative source",
        structured_content=content,
        source_type=BriefSourceType.MANUAL,
        source_reference=None,
        change_summary="Creative input",
    )
    provider = DeterministicFakeProvider(
        ProviderOutcome(ProviderOutcomeStatus.SUCCESS, '{"concepts":[]}')
    )
    service = CreativeApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory), provider
    )
    with pytest.raises(InvalidRequest):
        service.generate_concepts(
            context,
            project_id,
            brief.brief.id,
            brief.current_version.id,
            idempotency_key="bad-count",
        )
    service.provider = DeterministicFakeProvider(
        ProviderOutcome(
            ProviderOutcomeStatus.SUCCESS,
            json.dumps({"concepts": [{"schema_version": "1.0.0"}] * 3}),
        )
    )
    with pytest.raises(InvalidRequest, match="schema invalid"):
        service.generate_concepts(
            context,
            project_id,
            brief.brief.id,
            brief.current_version.id,
            idempotency_key="bad-count",
        )
    succeeded = _service(persistence_session_factory).generate_concepts(
        context, project_id, brief.brief.id, brief.current_version.id, idempotency_key="bad-count"
    )
    assert succeeded.replayed is False


def test_concurrent_same_key_concept_generation_creates_one_run(
    persistence_session_factory: SessionFactory, clean_database: None, tmp_path: Path
) -> None:
    del clean_database
    context, project_id, *_ = _source(persistence_session_factory, tmp_path)
    content = json.loads((FIXTURES / "valid-structured-brief-v1.json").read_text())
    brief = BriefApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    ).create_brief(
        context,
        project_id,
        title="Concurrent creative source",
        structured_content=content,
        source_type=BriefSourceType.MANUAL,
        source_reference=None,
        change_summary="Concurrent creative input",
    )
    service = _service(persistence_session_factory)

    def generate() -> ConceptGenerationResult:
        return service.generate_concepts(
            context,
            project_id,
            brief.brief.id,
            brief.current_version.id,
            idempotency_key="concurrent-concepts",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: generate(), range(2)))
    assert len({result.run.id for result in results}) == 1
    assert sum(result.replayed for result in results) == 1
