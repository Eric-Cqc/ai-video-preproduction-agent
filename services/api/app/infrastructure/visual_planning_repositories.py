from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services.api.app.application.errors import ResourceConflict
from services.api.app.domain import (
    CreativeRunStatus,
    ShotPlanRun,
    ShotPlanVersion,
    StoryboardRun,
    StoryboardVersion,
    VersionConflict,
    VisualPlanningOperation,
    VisualPlanningOperationStatus,
    VisualPlanningOperationType,
)
from services.api.app.infrastructure.models import (
    ShotPlanRunRecord,
    ShotPlanVersionRecord,
    StoryboardRunRecord,
    StoryboardVersionRecord,
    VisualPlanningOperationRecord,
)


def _flush(session: Session, record: object) -> None:
    session.add(record)
    try:
        session.flush()
    except Exception as error:
        raise ResourceConflict("visual planning artifact could not be persisted") from error


class SqlAlchemyStoryboardRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, value: StoryboardRun) -> StoryboardRun:
        _flush(self.session, StoryboardRunRecord(**_storyboard_run_values(value)))
        return value

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, value_id: UUID
    ) -> StoryboardRun | None:
        r = self.session.scalar(
            select(StoryboardRunRecord).where(
                StoryboardRunRecord.organization_id == organization_id,
                StoryboardRunRecord.workspace_id == workspace_id,
                StoryboardRunRecord.project_id == project_id,
                StoryboardRunRecord.id == value_id,
            )
        )
        return _to_storyboard_run(r) if r else None


class SqlAlchemyStoryboardVersionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, value: StoryboardVersion) -> StoryboardVersion:
        _flush(self.session, StoryboardVersionRecord(**_storyboard_version_values(value)))
        return value

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, value_id: UUID
    ) -> StoryboardVersion | None:
        r = self.session.scalar(
            select(StoryboardVersionRecord).where(
                StoryboardVersionRecord.organization_id == organization_id,
                StoryboardVersionRecord.workspace_id == workspace_id,
                StoryboardVersionRecord.project_id == project_id,
                StoryboardVersionRecord.id == value_id,
            )
        )
        return _to_storyboard_version(r) if r else None

    def get_for_run(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        storyboard_run_id: UUID,
        version_number: int,
    ) -> StoryboardVersion | None:
        r = self.session.scalar(
            select(StoryboardVersionRecord).where(
                StoryboardVersionRecord.organization_id == organization_id,
                StoryboardVersionRecord.workspace_id == workspace_id,
                StoryboardVersionRecord.project_id == project_id,
                StoryboardVersionRecord.storyboard_run_id == storyboard_run_id,
                StoryboardVersionRecord.version_number == version_number,
            )
        )
        return _to_storyboard_version(r) if r else None


class SqlAlchemyShotPlanRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, value: ShotPlanRun) -> ShotPlanRun:
        _flush(self.session, ShotPlanRunRecord(**_shot_run_values(value)))
        return value

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, value_id: UUID
    ) -> ShotPlanRun | None:
        r = self.session.scalar(
            select(ShotPlanRunRecord).where(
                ShotPlanRunRecord.organization_id == organization_id,
                ShotPlanRunRecord.workspace_id == workspace_id,
                ShotPlanRunRecord.project_id == project_id,
                ShotPlanRunRecord.id == value_id,
            )
        )
        return _to_shot_plan_run(r) if r else None


class SqlAlchemyShotPlanVersionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, value: ShotPlanVersion) -> ShotPlanVersion:
        _flush(self.session, ShotPlanVersionRecord(**_shot_version_values(value)))
        return value

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, value_id: UUID
    ) -> ShotPlanVersion | None:
        r = self.session.scalar(
            select(ShotPlanVersionRecord).where(
                ShotPlanVersionRecord.organization_id == organization_id,
                ShotPlanVersionRecord.workspace_id == workspace_id,
                ShotPlanVersionRecord.project_id == project_id,
                ShotPlanVersionRecord.id == value_id,
            )
        )
        return _to_shot_plan_version(r) if r else None

    def get_for_run(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        shot_plan_run_id: UUID,
        version_number: int,
    ) -> ShotPlanVersion | None:
        r = self.session.scalar(
            select(ShotPlanVersionRecord).where(
                ShotPlanVersionRecord.organization_id == organization_id,
                ShotPlanVersionRecord.workspace_id == workspace_id,
                ShotPlanVersionRecord.project_id == project_id,
                ShotPlanVersionRecord.shot_plan_run_id == shot_plan_run_id,
                ShotPlanVersionRecord.version_number == version_number,
            )
        )
        return _to_shot_plan_version(r) if r else None


class SqlAlchemyVisualPlanningOperationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def reserve(self, value: VisualPlanningOperation) -> VisualPlanningOperation | None:
        r = self.session.scalar(
            insert(VisualPlanningOperationRecord)
            .values(**_operation_values(value))
            .on_conflict_do_nothing()
            .returning(VisualPlanningOperationRecord)
        )
        return _to_visual_planning_operation(r) if r else None

    def get_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: VisualPlanningOperationType,
        idempotency_key: str,
    ) -> VisualPlanningOperation | None:
        r = self.session.scalar(
            select(VisualPlanningOperationRecord).where(
                VisualPlanningOperationRecord.organization_id == organization_id,
                VisualPlanningOperationRecord.workspace_id == workspace_id,
                VisualPlanningOperationRecord.project_id == project_id,
                VisualPlanningOperationRecord.operation == operation.value,
                VisualPlanningOperationRecord.idempotency_key == idempotency_key,
            )
        )
        return _to_visual_planning_operation(r) if r else None

    def finalize_accepted(
        self, value: VisualPlanningOperation, *, expected_version: int
    ) -> VisualPlanningOperation:
        r = self.session.scalar(
            update(VisualPlanningOperationRecord)
            .where(
                VisualPlanningOperationRecord.id == value.id,
                VisualPlanningOperationRecord.organization_id == value.organization_id,
                VisualPlanningOperationRecord.workspace_id == value.workspace_id,
                VisualPlanningOperationRecord.project_id == value.project_id,
                VisualPlanningOperationRecord.operation == value.operation.value,
                VisualPlanningOperationRecord.idempotency_key == value.idempotency_key,
                VisualPlanningOperationRecord.request_digest == value.request_digest,
                VisualPlanningOperationRecord.status == "reserved",
                VisualPlanningOperationRecord.version == expected_version,
            )
            .values(
                status="accepted",
                outcome_storyboard_run_id=value.outcome_storyboard_run_id,
                outcome_storyboard_version_id=value.outcome_storyboard_version_id,
                outcome_shot_plan_run_id=value.outcome_shot_plan_run_id,
                outcome_shot_plan_version_id=value.outcome_shot_plan_version_id,
                completed_at=value.completed_at,
                version=value.version,
            )
            .returning(VisualPlanningOperationRecord)
        )
        if r is None:
            raise VersionConflict("visual planning operation changed before finalization")
        return _to_visual_planning_operation(r)


def _storyboard_run_values(v: StoryboardRun) -> dict[str, object]:
    return {
        "id": v.id,
        "organization_id": v.organization_id,
        "workspace_id": v.workspace_id,
        "project_id": v.project_id,
        "brief_id": v.brief_id,
        "brief_version_id": v.brief_version_id,
        "concept_run_id": v.concept_run_id,
        "concept_candidate_id": v.concept_candidate_id,
        "concept_selection_id": v.concept_selection_id,
        "script_run_id": v.script_run_id,
        "script_version_id": v.script_version_id,
        "script_content_digest": v.script_content_digest,
        "instruction_template_id": v.instruction_template_id,
        "instruction_template_version": v.instruction_template_version,
        "provider_id": v.provider_id,
        "model_id": v.model_id,
        "status": v.status.value,
        "failure_category": v.failure_category,
        "created_by_actor_subject": v.created_by_actor_subject,
        "created_at": v.created_at,
        "completed_at": v.completed_at,
        "version": v.version,
    }


def _storyboard_version_values(v: StoryboardVersion) -> dict[str, object]:
    return {
        "id": v.id,
        "organization_id": v.organization_id,
        "workspace_id": v.workspace_id,
        "project_id": v.project_id,
        "storyboard_run_id": v.storyboard_run_id,
        "brief_id": v.brief_id,
        "brief_version_id": v.brief_version_id,
        "concept_run_id": v.concept_run_id,
        "concept_candidate_id": v.concept_candidate_id,
        "concept_selection_id": v.concept_selection_id,
        "script_run_id": v.script_run_id,
        "script_version_id": v.script_version_id,
        "version_number": v.version_number,
        "schema_version": v.schema_version,
        "content": v.content,
        "content_digest": v.content_digest,
        "total_duration_seconds": v.total_duration_seconds,
        "scene_count": v.scene_count,
        "created_at": v.created_at,
    }


def _shot_run_values(v: ShotPlanRun) -> dict[str, object]:
    return {
        "id": v.id,
        "organization_id": v.organization_id,
        "workspace_id": v.workspace_id,
        "project_id": v.project_id,
        "storyboard_run_id": v.storyboard_run_id,
        "storyboard_version_id": v.storyboard_version_id,
        "script_run_id": v.script_run_id,
        "script_version_id": v.script_version_id,
        "brief_id": v.brief_id,
        "brief_version_id": v.brief_version_id,
        "concept_run_id": v.concept_run_id,
        "concept_candidate_id": v.concept_candidate_id,
        "concept_selection_id": v.concept_selection_id,
        "storyboard_content_digest": v.storyboard_content_digest,
        "instruction_template_id": v.instruction_template_id,
        "instruction_template_version": v.instruction_template_version,
        "provider_id": v.provider_id,
        "model_id": v.model_id,
        "status": v.status.value,
        "failure_category": v.failure_category,
        "created_by_actor_subject": v.created_by_actor_subject,
        "created_at": v.created_at,
        "completed_at": v.completed_at,
        "version": v.version,
    }


def _shot_version_values(v: ShotPlanVersion) -> dict[str, object]:
    return {
        "id": v.id,
        "organization_id": v.organization_id,
        "workspace_id": v.workspace_id,
        "project_id": v.project_id,
        "shot_plan_run_id": v.shot_plan_run_id,
        "storyboard_run_id": v.storyboard_run_id,
        "storyboard_version_id": v.storyboard_version_id,
        "script_run_id": v.script_run_id,
        "script_version_id": v.script_version_id,
        "brief_id": v.brief_id,
        "brief_version_id": v.brief_version_id,
        "concept_run_id": v.concept_run_id,
        "concept_candidate_id": v.concept_candidate_id,
        "concept_selection_id": v.concept_selection_id,
        "version_number": v.version_number,
        "schema_version": v.schema_version,
        "content": v.content,
        "content_digest": v.content_digest,
        "total_duration_seconds": v.total_duration_seconds,
        "scene_count": v.scene_count,
        "shot_count": v.shot_count,
        "created_at": v.created_at,
    }


def _operation_values(v: VisualPlanningOperation) -> dict[str, object]:
    return {
        "id": v.id,
        "organization_id": v.organization_id,
        "workspace_id": v.workspace_id,
        "project_id": v.project_id,
        "operation": v.operation.value,
        "idempotency_key": v.idempotency_key,
        "request_digest": v.request_digest,
        "status": v.status.value,
        "outcome_storyboard_run_id": v.outcome_storyboard_run_id,
        "outcome_storyboard_version_id": v.outcome_storyboard_version_id,
        "outcome_shot_plan_run_id": v.outcome_shot_plan_run_id,
        "outcome_shot_plan_version_id": v.outcome_shot_plan_version_id,
        "submitted_by_actor_subject": v.submitted_by_actor_subject,
        "submitted_at": v.submitted_at,
        "completed_at": v.completed_at,
        "correlation_id": v.correlation_id,
        "version": v.version,
    }


def _to_storyboard_run(r: StoryboardRunRecord) -> StoryboardRun:
    return StoryboardRun(
        r.id,
        r.organization_id,
        r.workspace_id,
        r.project_id,
        r.brief_id,
        r.brief_version_id,
        r.concept_run_id,
        r.concept_candidate_id,
        r.concept_selection_id,
        r.script_run_id,
        r.script_version_id,
        r.script_content_digest,
        r.instruction_template_id,
        r.instruction_template_version,
        r.provider_id,
        r.model_id,
        CreativeRunStatus(r.status),
        r.failure_category,
        r.created_by_actor_subject,
        r.created_at,
        r.completed_at,
        r.version,
    )


def _to_storyboard_version(r: StoryboardVersionRecord) -> StoryboardVersion:
    return StoryboardVersion(
        r.id,
        r.organization_id,
        r.workspace_id,
        r.project_id,
        r.storyboard_run_id,
        r.brief_id,
        r.brief_version_id,
        r.concept_run_id,
        r.concept_candidate_id,
        r.concept_selection_id,
        r.script_run_id,
        r.script_version_id,
        r.version_number,
        r.schema_version,
        r.content,
        r.content_digest,
        r.total_duration_seconds,
        r.scene_count,
        r.created_at,
    )


def _to_shot_plan_run(r: ShotPlanRunRecord) -> ShotPlanRun:
    return ShotPlanRun(
        r.id,
        r.organization_id,
        r.workspace_id,
        r.project_id,
        r.storyboard_run_id,
        r.storyboard_version_id,
        r.script_run_id,
        r.script_version_id,
        r.brief_id,
        r.brief_version_id,
        r.concept_run_id,
        r.concept_candidate_id,
        r.concept_selection_id,
        r.storyboard_content_digest,
        r.instruction_template_id,
        r.instruction_template_version,
        r.provider_id,
        r.model_id,
        CreativeRunStatus(r.status),
        r.failure_category,
        r.created_by_actor_subject,
        r.created_at,
        r.completed_at,
        r.version,
    )


def _to_shot_plan_version(r: ShotPlanVersionRecord) -> ShotPlanVersion:
    return ShotPlanVersion(
        r.id,
        r.organization_id,
        r.workspace_id,
        r.project_id,
        r.shot_plan_run_id,
        r.storyboard_run_id,
        r.storyboard_version_id,
        r.script_run_id,
        r.script_version_id,
        r.brief_id,
        r.brief_version_id,
        r.concept_run_id,
        r.concept_candidate_id,
        r.concept_selection_id,
        r.version_number,
        r.schema_version,
        r.content,
        r.content_digest,
        r.total_duration_seconds,
        r.scene_count,
        r.shot_count,
        r.created_at,
    )


def _to_visual_planning_operation(r: VisualPlanningOperationRecord) -> VisualPlanningOperation:
    return VisualPlanningOperation(
        r.id,
        r.organization_id,
        r.workspace_id,
        r.project_id,
        VisualPlanningOperationType(r.operation),
        r.idempotency_key,
        r.request_digest,
        VisualPlanningOperationStatus(r.status),
        r.outcome_storyboard_run_id,
        r.outcome_storyboard_version_id,
        r.outcome_shot_plan_run_id,
        r.outcome_shot_plan_version_id,
        r.submitted_by_actor_subject,
        r.submitted_at,
        r.completed_at,
        r.correlation_id,
        r.version,
    )
