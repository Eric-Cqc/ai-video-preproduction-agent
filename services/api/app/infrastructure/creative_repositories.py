from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services.api.app.application.errors import ResourceConflict
from services.api.app.domain import (
    CreativeConceptCandidate,
    CreativeConceptRun,
    CreativeConceptSelection,
    CreativeGenerationOperation,
    CreativeGenerationOperationStatus,
    CreativeGenerationOperationType,
    CreativeRunStatus,
    ScriptRun,
    ScriptVersion,
    VersionConflict,
)
from services.api.app.infrastructure.models import (
    CreativeConceptCandidateRecord,
    CreativeConceptRunRecord,
    CreativeConceptSelectionRecord,
    CreativeGenerationOperationRecord,
    ScriptRunRecord,
    ScriptVersionRecord,
)


def _add(session: Session, record: object, value: object) -> object:
    session.add(record)
    try:
        session.flush()
    except Exception as error:
        raise ResourceConflict("creative artifact could not be persisted") from error
    return value


class SqlAlchemyCreativeConceptRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, run: CreativeConceptRun) -> CreativeConceptRun:
        return _add(self.session, CreativeConceptRunRecord(**_run_values(run)), run)  # type: ignore[return-value]

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, run_id: UUID
    ) -> CreativeConceptRun | None:
        record = self.session.scalar(
            select(CreativeConceptRunRecord).where(
                CreativeConceptRunRecord.organization_id == organization_id,
                CreativeConceptRunRecord.workspace_id == workspace_id,
                CreativeConceptRunRecord.project_id == project_id,
                CreativeConceptRunRecord.id == run_id,
            )
        )
        return _concept_run(record) if record else None


class SqlAlchemyCreativeConceptCandidateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, candidate: CreativeConceptCandidate) -> CreativeConceptCandidate:
        return _add(
            self.session, CreativeConceptCandidateRecord(**_candidate_values(candidate)), candidate
        )  # type: ignore[return-value]

    def get(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        run_id: UUID,
        candidate_id: UUID,
    ) -> CreativeConceptCandidate | None:
        record = self.session.scalar(
            select(CreativeConceptCandidateRecord).where(
                CreativeConceptCandidateRecord.organization_id == organization_id,
                CreativeConceptCandidateRecord.workspace_id == workspace_id,
                CreativeConceptCandidateRecord.project_id == project_id,
                CreativeConceptCandidateRecord.concept_run_id == run_id,
                CreativeConceptCandidateRecord.id == candidate_id,
            )
        )
        return _candidate(record) if record else None

    def list_for_run(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, run_id: UUID
    ) -> list[CreativeConceptCandidate]:
        return [
            _candidate(value)
            for value in self.session.scalars(
                select(CreativeConceptCandidateRecord)
                .where(
                    CreativeConceptCandidateRecord.organization_id == organization_id,
                    CreativeConceptCandidateRecord.workspace_id == workspace_id,
                    CreativeConceptCandidateRecord.project_id == project_id,
                    CreativeConceptCandidateRecord.concept_run_id == run_id,
                )
                .order_by(CreativeConceptCandidateRecord.candidate_index)
            )
        ]


class SqlAlchemyCreativeConceptSelectionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, selection: CreativeConceptSelection) -> CreativeConceptSelection:
        return _add(
            self.session, CreativeConceptSelectionRecord(**_selection_values(selection)), selection
        )  # type: ignore[return-value]

    def get_for_run(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, run_id: UUID
    ) -> CreativeConceptSelection | None:
        record = self.session.scalar(
            select(CreativeConceptSelectionRecord).where(
                CreativeConceptSelectionRecord.organization_id == organization_id,
                CreativeConceptSelectionRecord.workspace_id == workspace_id,
                CreativeConceptSelectionRecord.project_id == project_id,
                CreativeConceptSelectionRecord.concept_run_id == run_id,
            )
        )
        return _selection(record) if record else None


class SqlAlchemyScriptRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, run: ScriptRun) -> ScriptRun:
        return _add(self.session, ScriptRunRecord(**_script_run_values(run)), run)  # type: ignore[return-value]

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, run_id: UUID
    ) -> ScriptRun | None:
        record = self.session.scalar(
            select(ScriptRunRecord).where(
                ScriptRunRecord.organization_id == organization_id,
                ScriptRunRecord.workspace_id == workspace_id,
                ScriptRunRecord.project_id == project_id,
                ScriptRunRecord.id == run_id,
            )
        )
        return _script_run(record) if record else None


class SqlAlchemyScriptVersionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, version: ScriptVersion) -> ScriptVersion:
        return _add(self.session, ScriptVersionRecord(**_script_version_values(version)), version)  # type: ignore[return-value]

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, version_id: UUID
    ) -> ScriptVersion | None:
        record = self.session.scalar(
            select(ScriptVersionRecord).where(
                ScriptVersionRecord.organization_id == organization_id,
                ScriptVersionRecord.workspace_id == workspace_id,
                ScriptVersionRecord.project_id == project_id,
                ScriptVersionRecord.id == version_id,
            )
        )
        return _script_version(record) if record else None


class SqlAlchemyCreativeGenerationOperationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def reserve(self, operation: CreativeGenerationOperation) -> CreativeGenerationOperation | None:
        record = self.session.scalar(
            insert(CreativeGenerationOperationRecord)
            .values(**_operation_values(operation))
            .on_conflict_do_nothing()
            .returning(CreativeGenerationOperationRecord)
        )
        return _operation(record) if record else None

    def get_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: CreativeGenerationOperationType,
        idempotency_key: str,
    ) -> CreativeGenerationOperation | None:
        record = self.session.scalar(
            select(CreativeGenerationOperationRecord).where(
                CreativeGenerationOperationRecord.organization_id == organization_id,
                CreativeGenerationOperationRecord.workspace_id == workspace_id,
                CreativeGenerationOperationRecord.project_id == project_id,
                CreativeGenerationOperationRecord.operation == operation.value,
                CreativeGenerationOperationRecord.idempotency_key == idempotency_key,
            )
        )
        return _operation(record) if record else None

    def finalize_accepted(
        self, operation: CreativeGenerationOperation, *, expected_version: int
    ) -> CreativeGenerationOperation:
        record = self.session.scalar(
            update(CreativeGenerationOperationRecord)
            .where(
                CreativeGenerationOperationRecord.id == operation.id,
                CreativeGenerationOperationRecord.organization_id == operation.organization_id,
                CreativeGenerationOperationRecord.workspace_id == operation.workspace_id,
                CreativeGenerationOperationRecord.project_id == operation.project_id,
                CreativeGenerationOperationRecord.operation == operation.operation.value,
                CreativeGenerationOperationRecord.idempotency_key == operation.idempotency_key,
                CreativeGenerationOperationRecord.request_digest == operation.request_digest,
                CreativeGenerationOperationRecord.status == "reserved",
                CreativeGenerationOperationRecord.version == expected_version,
            )
            .values(
                status="accepted",
                outcome_concept_run_id=operation.outcome_concept_run_id,
                outcome_candidate_id=operation.outcome_candidate_id,
                outcome_selection_id=operation.outcome_selection_id,
                outcome_script_run_id=operation.outcome_script_run_id,
                outcome_script_version_id=operation.outcome_script_version_id,
                completed_at=operation.completed_at,
                version=operation.version,
            )
            .returning(CreativeGenerationOperationRecord)
        )
        if record is None:
            raise VersionConflict("creative operation changed before finalization")
        return _operation(record)


def _run_values(value: CreativeConceptRun) -> dict[str, object]:
    return {
        key: getattr(value, key) if key not in {"status"} else value.status.value
        for key in value.__dataclass_fields__
        if key != "request_digest"
    }


def _candidate_values(value: CreativeConceptCandidate) -> dict[str, object]:
    return {key: getattr(value, key) for key in value.__dataclass_fields__}


def _selection_values(value: CreativeConceptSelection) -> dict[str, object]:
    return {key: getattr(value, key) for key in value.__dataclass_fields__}


def _script_run_values(value: ScriptRun) -> dict[str, object]:
    return {
        key: (getattr(value, key).value if key == "status" else getattr(value, key))
        for key in value.__dataclass_fields__
        if key != "request_digest"
    }


def _script_version_values(value: ScriptVersion) -> dict[str, object]:
    return {key: getattr(value, key) for key in value.__dataclass_fields__}


def _operation_values(value: CreativeGenerationOperation) -> dict[str, object]:
    return {
        key: (getattr(value, key).value if key in {"operation", "status"} else getattr(value, key))
        for key in value.__dataclass_fields__
    }


def _concept_run(r: CreativeConceptRunRecord) -> CreativeConceptRun:
    return CreativeConceptRun(
        r.id,
        r.organization_id,
        r.workspace_id,
        r.project_id,
        r.brief_id,
        r.brief_version_id,
        r.brief_content_digest,
        r.instruction_template_id,
        r.instruction_template_version,
        r.provider_id,
        r.model_id,
        "",
        CreativeRunStatus(r.status),
        r.failure_category,
        r.candidate_count,
        r.created_by_actor_subject,
        r.created_at,
        r.completed_at,
        r.version,
    )


def _candidate(r: CreativeConceptCandidateRecord) -> CreativeConceptCandidate:
    return CreativeConceptCandidate(
        r.id,
        r.organization_id,
        r.workspace_id,
        r.project_id,
        r.concept_run_id,
        r.candidate_index,
        r.schema_version,
        r.content,
        r.content_digest,
        r.created_at,
    )


def _selection(r: CreativeConceptSelectionRecord) -> CreativeConceptSelection:
    return CreativeConceptSelection(
        r.id,
        r.organization_id,
        r.workspace_id,
        r.project_id,
        r.concept_run_id,
        r.concept_candidate_id,
        r.selected_by_actor_subject,
        r.selected_at,
        r.version,
    )


def _script_run(r: ScriptRunRecord) -> ScriptRun:
    return ScriptRun(
        r.id,
        r.organization_id,
        r.workspace_id,
        r.project_id,
        r.brief_id,
        r.brief_version_id,
        r.concept_run_id,
        r.concept_candidate_id,
        r.concept_selection_id,
        r.brief_content_digest,
        r.concept_content_digest,
        r.instruction_template_id,
        r.instruction_template_version,
        r.provider_id,
        r.model_id,
        "",
        CreativeRunStatus(r.status),
        r.failure_category,
        r.created_by_actor_subject,
        r.created_at,
        r.completed_at,
        r.version,
    )


def _script_version(r: ScriptVersionRecord) -> ScriptVersion:
    return ScriptVersion(
        r.id,
        r.organization_id,
        r.workspace_id,
        r.project_id,
        r.script_run_id,
        r.brief_id,
        r.brief_version_id,
        r.concept_run_id,
        r.concept_candidate_id,
        r.concept_selection_id,
        r.version_number,
        r.schema_version,
        r.content,
        r.content_digest,
        r.created_at,
    )


def _operation(r: CreativeGenerationOperationRecord) -> CreativeGenerationOperation:
    return CreativeGenerationOperation(
        r.id,
        r.organization_id,
        r.workspace_id,
        r.project_id,
        CreativeGenerationOperationType(r.operation),
        r.idempotency_key,
        r.request_digest,
        CreativeGenerationOperationStatus(r.status),
        r.outcome_concept_run_id,
        r.outcome_candidate_id,
        r.outcome_selection_id,
        r.outcome_script_run_id,
        r.outcome_script_version_id,
        r.submitted_by_actor_subject,
        r.submitted_at,
        r.completed_at,
        r.correlation_id,
        r.version,
    )
