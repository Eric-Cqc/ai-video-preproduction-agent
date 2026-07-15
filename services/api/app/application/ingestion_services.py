import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from foundation_contracts import STRUCTURED_BRIEF_SCHEMA_VERSION

from services.api.app.application.brief_services import BriefBundle
from services.api.app.application.context import TenantContext
from services.api.app.application.errors import InvalidRequest, ResourceConflict, ResourceNotFound
from services.api.app.application.ingestion_normalization import canonicalize_structured_brief
from services.api.app.application.services import (
    MUTATION_ROLES,
    READ_ROLES,
    Clock,
    IdFactory,
    utc_now,
)
from services.api.app.application.uow import UnitOfWork
from services.api.app.domain import (
    AuditEvent,
    Brief,
    BriefIngestion,
    BriefIngestionOperation,
    BriefIngestionSourceType,
    BriefIngestionStatus,
    BriefSourceType,
    BriefStatus,
    BriefVersion,
    BriefVersionLifecycle,
    Membership,
    OrganizationStatus,
    ProjectStatus,
    RequirementIssue,
    RequirementIssueStatus,
    WorkspaceStatus,
)
from services.api.app.domain.brief_issues import detect_requirement_issues

SOURCE_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")


@dataclass(frozen=True, slots=True)
class IngestionResult:
    ingestion: BriefIngestion
    bundle: BriefBundle
    replayed: bool


class BriefIngestionApplicationService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        clock: Clock = utc_now,
        id_factory: IdFactory = uuid4,
    ) -> None:
        self.uow_factory = uow_factory
        self.clock = clock
        self.id_factory = id_factory

    def create_brief(
        self,
        context: TenantContext,
        project_id: UUID,
        *,
        idempotency_key: str,
        title: str,
        structured_content: dict[str, object],
        source_type: BriefIngestionSourceType,
        source_reference: str | None,
        change_summary: str,
    ) -> IngestionResult:
        self._validate_text_bounds(title, change_summary)
        now = self.clock()
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id)
            content, digest = self._prepare_digest(
                BriefIngestionOperation.CREATE_BRIEF,
                structured_content,
                {
                    "title": title,
                    "source_type": source_type.value,
                    "source_reference": source_reference,
                    "change_summary": change_summary,
                },
            )
            replay = self._reserve_or_replay(
                uow,
                context,
                project_id,
                BriefIngestionOperation.CREATE_BRIEF,
                idempotency_key,
                digest,
                source_type,
                source_reference,
                now,
            )
            if replay is not None:
                return replay
            ingestion = self._require_reservation(
                uow, context, project_id, BriefIngestionOperation.CREATE_BRIEF, idempotency_key
            )
            brief_id, version_id = self.id_factory(), self.id_factory()
            brief = Brief(
                brief_id,
                context.organization_id,
                context.workspace_id,
                project_id,
                title,
                BriefStatus.DRAFT,
                version_id,
                1,
                context.actor_subject,
                now,
                now,
                1,
            )
            version = self._version(
                context,
                project_id,
                brief_id,
                version_id,
                1,
                content,
                source_reference,
                change_summary,
                None,
                now,
            )
            saved_brief = uow.briefs.add(brief)
            saved_version = uow.brief_versions.add(version)
            issues = self._issues(uow, context, saved_version, now)
            accepted = uow.brief_ingestions.finalize_accepted(
                ingestion,
                brief_id=brief_id,
                brief_version_id=version_id,
                completed_at=now,
                expected_version=1,
            )
            uow.audit_events.append(
                self._audit(
                    context,
                    brief_id,
                    accepted,
                    saved_version,
                    len(issues),
                    saved_brief.version,
                    now,
                )
            )
            return IngestionResult(accepted, BriefBundle(saved_brief, saved_version, issues), False)

    def create_version(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        *,
        idempotency_key: str,
        expected_brief_version: int,
        expected_current_version_id: UUID,
        source_version_id: UUID,
        structured_content: dict[str, object],
        source_type: BriefIngestionSourceType,
        source_reference: str | None,
        change_summary: str,
    ) -> IngestionResult:
        self._validate_text_bounds(None, change_summary)
        now = self.clock()
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id)
            visible_brief = self._require_brief(uow, context, project_id, brief_id)
            content, digest = self._prepare_digest(
                BriefIngestionOperation.CREATE_VERSION,
                structured_content,
                {
                    "brief_id": str(brief_id),
                    "expected_brief_version": expected_brief_version,
                    "expected_current_version_id": str(expected_current_version_id),
                    "source_version_id": str(source_version_id),
                    "source_type": source_type.value,
                    "source_reference": source_reference,
                    "change_summary": change_summary,
                },
            )
            replay = self._reserve_or_replay(
                uow,
                context,
                project_id,
                BriefIngestionOperation.CREATE_VERSION,
                idempotency_key,
                digest,
                source_type,
                source_reference,
                now,
            )
            if replay is not None:
                return replay
            ingestion = self._require_reservation(
                uow, context, project_id, BriefIngestionOperation.CREATE_VERSION, idempotency_key
            )
            if source_version_id != visible_brief.current_version_id:
                raise ResourceConflict(
                    "source version is no longer current", code="version_conflict"
                )
            old_version = self._require_version(
                uow, context, project_id, visible_brief, source_version_id
            )
            new_version_id = self.id_factory()
            updated = visible_brief.new_version(
                expected_version=expected_brief_version, new_version_id=new_version_id, now=now
            )
            saved_brief = uow.briefs.update(
                updated,
                expected_version=expected_brief_version,
                expected_current_version_id=expected_current_version_id,
            )
            if old_version.lifecycle_state is not BriefVersionLifecycle.APPROVED:
                uow.brief_versions.supersede(old_version.supersede())
            version = self._version(
                context,
                project_id,
                brief_id,
                new_version_id,
                saved_brief.latest_version_number,
                content,
                source_reference,
                change_summary,
                source_version_id,
                now,
            )
            saved_version = uow.brief_versions.add(version)
            issues = self._issues(uow, context, saved_version, now)
            accepted = uow.brief_ingestions.finalize_accepted(
                ingestion,
                brief_id=brief_id,
                brief_version_id=new_version_id,
                completed_at=now,
                expected_version=1,
            )
            uow.audit_events.append(
                self._audit(
                    context,
                    brief_id,
                    accepted,
                    saved_version,
                    len(issues),
                    saved_brief.version,
                    now,
                )
            )
            return IngestionResult(accepted, BriefBundle(saved_brief, saved_version, issues), False)

    def get(self, context: TenantContext, project_id: UUID, ingestion_id: UUID) -> IngestionResult:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, mutable=False)
            ingestion = uow.brief_ingestions.get(
                context.organization_id, context.workspace_id, project_id, ingestion_id
            )
            if ingestion is None or ingestion.status is not BriefIngestionStatus.ACCEPTED:
                raise ResourceNotFound("ingestion is not accessible")
            return self._result(uow, context, ingestion, replayed=False)

    def _reserve_or_replay(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        operation: BriefIngestionOperation,
        key: str,
        digest: str,
        source_type: BriefIngestionSourceType,
        source_reference: str | None,
        now: datetime,
    ) -> IngestionResult | None:
        reservation = BriefIngestion(
            self.id_factory(),
            context.organization_id,
            context.workspace_id,
            project_id,
            None,
            None,
            operation,
            key,
            source_type,
            source_reference,
            digest,
            STRUCTURED_BRIEF_SCHEMA_VERSION,
            BriefIngestionStatus.RESERVED,
            None,
            None,
            context.actor_subject,
            now,
            None,
            context.correlation_id,
            1,
        )
        won = uow.brief_ingestions.reserve(reservation)
        if won is not None:
            return None
        existing = uow.brief_ingestions.get_by_idempotency_key(
            context.organization_id, context.workspace_id, project_id, operation, key
        )
        if existing is None:
            raise ResourceConflict("idempotency reservation could not be resolved")
        if existing.payload_digest != digest:
            raise ResourceConflict(
                "idempotency key was used for a different request", code="idempotency_conflict"
            )
        if existing.status is not BriefIngestionStatus.ACCEPTED:
            raise ResourceConflict("idempotency reservation is not complete")
        return self._result(uow, context, existing, replayed=True)

    def _result(
        self, uow: UnitOfWork, context: TenantContext, ingestion: BriefIngestion, *, replayed: bool
    ) -> IngestionResult:
        assert ingestion.brief_id is not None and ingestion.brief_version_id is not None
        brief = self._require_brief(uow, context, ingestion.project_id, ingestion.brief_id)
        version = self._require_version(
            uow, context, ingestion.project_id, brief, ingestion.brief_version_id
        )
        issues = uow.requirement_issues.list(
            context.organization_id,
            context.workspace_id,
            ingestion.project_id,
            brief.id,
            version.id,
        )
        return IngestionResult(ingestion, BriefBundle(brief, version, issues), replayed)

    def _prepare_digest(
        self,
        operation: BriefIngestionOperation,
        content: dict[str, object],
        metadata: dict[str, object],
    ) -> tuple[dict[str, object], str]:
        self._validate_source_reference(cast_str(metadata.get("source_reference")))
        canonical, _ = canonicalize_structured_brief(content)
        encoded = json.dumps(
            {"operation": operation.value, "structured_content": canonical, **metadata},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return canonical, hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _validate_source_reference(value: str | None) -> None:
        forbidden_prefixes = ("authorization:", "bearer:", "postgresql:", "postgres:")
        if value is not None and (
            not SOURCE_REFERENCE_PATTERN.fullmatch(value)
            or value.lower().startswith(forbidden_prefixes)
        ):
            raise InvalidRequest("source_reference must be an opaque identifier")

    @staticmethod
    def _validate_text_bounds(title: str | None, change_summary: str) -> None:
        if title is not None and not 1 <= len(title) <= 200:
            raise InvalidRequest("title is outside the allowed length")
        if not 1 <= len(change_summary) <= 500:
            raise InvalidRequest("change_summary is outside the allowed length")

    @staticmethod
    def _require_project_access(
        uow: UnitOfWork, context: TenantContext, project_id: UUID, *, mutable: bool = True
    ) -> None:
        organization = uow.organizations.get(context.organization_id)
        workspace = uow.workspaces.get(context.organization_id, context.workspace_id)
        membership: Membership | None = uow.memberships.find_effective(
            context.organization_id, context.workspace_id, context.actor_subject
        )
        project = uow.projects.get(context.organization_id, context.workspace_id, project_id)
        if (
            organization is None
            or organization.status is not OrganizationStatus.ACTIVE
            or workspace is None
            or workspace.status is not WorkspaceStatus.ACTIVE
            or membership is None
            or membership.role not in (MUTATION_ROLES if mutable else READ_ROLES)
            or project is None
        ):
            raise ResourceNotFound("project is not accessible")
        if mutable and project.status is ProjectStatus.ARCHIVED:
            raise ResourceConflict("archived projects cannot be changed", code="project_archived")

    @staticmethod
    def _require_brief(
        uow: UnitOfWork, context: TenantContext, project_id: UUID, brief_id: UUID
    ) -> Brief:
        brief = uow.briefs.get(context.organization_id, context.workspace_id, project_id, brief_id)
        if brief is None:
            raise ResourceNotFound("brief is not accessible")
        return brief

    @staticmethod
    def _require_version(
        uow: UnitOfWork, context: TenantContext, project_id: UUID, brief: Brief, version_id: UUID
    ) -> BriefVersion:
        version = uow.brief_versions.get(
            context.organization_id, context.workspace_id, project_id, brief.id, version_id
        )
        if version is None:
            raise ResourceNotFound("brief version is not accessible")
        return version

    def _version(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
        number: int,
        content: dict[str, object],
        source_reference: str | None,
        change_summary: str,
        supersedes: UUID | None,
        now: datetime,
    ) -> BriefVersion:
        return BriefVersion(
            version_id,
            context.organization_id,
            context.workspace_id,
            project_id,
            brief_id,
            number,
            BriefVersionLifecycle.DRAFT,
            content,
            BriefSourceType.IMPORTED_STRUCTURED,
            source_reference,
            change_summary,
            context.actor_subject,
            now,
            None,
            None,
            None,
            supersedes,
            STRUCTURED_BRIEF_SCHEMA_VERSION,
        )

    def _issues(
        self, uow: UnitOfWork, context: TenantContext, version: BriefVersion, now: datetime
    ) -> list[RequirementIssue]:
        result = []
        for found in detect_requirement_issues(version.structured_content):
            result.append(
                uow.requirement_issues.add(
                    RequirementIssue(
                        self.id_factory(),
                        context.organization_id,
                        context.workspace_id,
                        version.project_id,
                        version.brief_id,
                        version.id,
                        found.issue_type,
                        found.field_path,
                        found.severity,
                        found.message,
                        RequirementIssueStatus.OPEN,
                        None,
                        "system:deterministic-checker",
                        None,
                        now,
                        None,
                        1,
                    )
                )
            )
        return result

    def _audit(
        self,
        context: TenantContext,
        brief_id: UUID,
        ingestion: BriefIngestion,
        version: BriefVersion,
        issue_count: int,
        aggregate_version: int,
        now: datetime,
    ) -> AuditEvent:
        return AuditEvent(
            self.id_factory(),
            context.organization_id,
            context.workspace_id,
            context.actor_subject,
            "brief",
            brief_id,
            "brief.ingestion_accepted",
            {
                "ingestion_id": str(ingestion.id),
                "operation": ingestion.operation.value,
                "schema_version": ingestion.schema_version,
                "source_type": ingestion.source_type.value,
                "brief_version_number": version.version_number,
                "issue_count": issue_count,
                "aggregate_version": aggregate_version,
            },
            now,
            context.correlation_id,
        )

    def _require_reservation(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        operation: BriefIngestionOperation,
        key: str,
    ) -> BriefIngestion:
        ingestion = uow.brief_ingestions.get_by_idempotency_key(
            context.organization_id, context.workspace_id, project_id, operation, key
        )
        if ingestion is None or ingestion.status is not BriefIngestionStatus.RESERVED:
            raise ResourceConflict("ingestion reservation was lost")
        return ingestion


def cast_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
