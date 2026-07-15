import json
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID, uuid4

from foundation_contracts import STRUCTURED_BRIEF_SCHEMA_VERSION, validate_structured_brief
from jsonschema import ValidationError

from services.api.app.application.context import TenantContext
from services.api.app.application.errors import InvalidRequest, ResourceConflict, ResourceNotFound
from services.api.app.application.services import (
    ADMIN_ROLES,
    MUTATION_ROLES,
    READ_ROLES,
    Clock,
    IdFactory,
    utc_now,
)
from services.api.app.application.uow import UnitOfWork
from services.api.app.domain import (
    ApprovalBlocked,
    AuditEvent,
    Brief,
    BriefSourceType,
    BriefStatus,
    BriefVersion,
    BriefVersionLifecycle,
    Membership,
    MembershipRole,
    OrganizationStatus,
    Project,
    ProjectStatus,
    RequirementIssue,
    RequirementIssueSeverity,
    RequirementIssueStatus,
    RequirementIssueType,
    WorkspaceStatus,
)
from services.api.app.domain.brief_issues import detect_requirement_issues

UnitOfWorkFactory = Callable[[], UnitOfWork]
MAX_STRUCTURED_CONTENT_BYTES = 128 * 1024
SOURCE_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")


@dataclass(frozen=True, slots=True)
class BriefBundle:
    brief: Brief
    current_version: BriefVersion
    issues: list[RequirementIssue]


class BriefApplicationService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
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
        title: str,
        structured_content: dict[str, object],
        source_type: BriefSourceType,
        source_reference: str | None,
        change_summary: str,
    ) -> BriefBundle:
        self._validate_content(structured_content)
        self._validate_source_reference(source_reference)
        now = self.clock()
        brief_id = self.id_factory()
        version_id = self.id_factory()
        brief = Brief(
            id=brief_id,
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            project_id=project_id,
            title=title,
            status=BriefStatus.DRAFT,
            current_version_id=version_id,
            latest_version_number=1,
            created_by_actor_subject=context.actor_subject,
            created_at=now,
            updated_at=now,
            version=1,
        )
        version = self._new_version_entity(
            context,
            project_id,
            brief_id,
            version_id,
            version_number=1,
            structured_content=structured_content,
            source_type=source_type,
            source_reference=source_reference,
            change_summary=change_summary,
            supersedes_version_id=None,
            now=now,
        )
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, MUTATION_ROLES, mutable=True)
            result = uow.briefs.add(brief)
            saved_version = uow.brief_versions.add(version)
            issues = self._add_detected_issues(uow, context, saved_version, now)
            uow.audit_events.append(
                self._event(
                    context,
                    brief_id,
                    "brief.created",
                    {
                        "brief_version": 1,
                        "content_schema_version": STRUCTURED_BRIEF_SCHEMA_VERSION,
                        "detected_issue_count": len(issues),
                        "version": 1,
                    },
                    now,
                )
            )
            return BriefBundle(result, saved_version, issues)

    def get_brief(self, context: TenantContext, project_id: UUID, brief_id: UUID) -> BriefBundle:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, READ_ROLES)
            brief = self._require_brief(uow, context, project_id, brief_id)
            version = self._require_version(
                uow, context, project_id, brief, brief.current_version_id
            )
            issues = uow.requirement_issues.list(
                context.organization_id,
                context.workspace_id,
                project_id,
                brief_id,
                version.id,
            )
            return BriefBundle(brief, version, issues)

    def list_briefs(self, context: TenantContext, project_id: UUID) -> list[Brief]:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, READ_ROLES)
            return uow.briefs.list(context.organization_id, context.workspace_id, project_id)

    def list_versions(
        self, context: TenantContext, project_id: UUID, brief_id: UUID
    ) -> list[BriefVersion]:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, READ_ROLES)
            self._require_brief(uow, context, project_id, brief_id)
            return uow.brief_versions.list(
                context.organization_id, context.workspace_id, project_id, brief_id
            )

    def get_version(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
    ) -> BriefVersion:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, READ_ROLES)
            brief = self._require_brief(uow, context, project_id, brief_id)
            return self._require_version(uow, context, project_id, brief, version_id)

    def list_issues(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
    ) -> list[RequirementIssue]:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, READ_ROLES)
            brief = self._require_brief(uow, context, project_id, brief_id)
            self._require_version(uow, context, project_id, brief, version_id)
            return uow.requirement_issues.list(
                context.organization_id,
                context.workspace_id,
                project_id,
                brief_id,
                version_id,
            )

    def get_issue(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
        issue_id: UUID,
    ) -> RequirementIssue:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, READ_ROLES)
            brief = self._require_brief(uow, context, project_id, brief_id)
            self._require_version(uow, context, project_id, brief, version_id)
            issue = uow.requirement_issues.get(
                context.organization_id,
                context.workspace_id,
                project_id,
                brief_id,
                version_id,
                issue_id,
            )
            if issue is None:
                raise ResourceNotFound("requirement issue is not accessible")
            return issue

    def list_audit_events(
        self, context: TenantContext, project_id: UUID, brief_id: UUID
    ) -> list[AuditEvent]:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, READ_ROLES)
            self._require_brief(uow, context, project_id, brief_id)
            return uow.audit_events.list_for_brief(
                context.organization_id, context.workspace_id, brief_id
            )

    def create_version(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        *,
        expected_brief_version: int,
        expected_current_version_id: UUID,
        source_version_id: UUID,
        structured_content: dict[str, object],
        source_type: BriefSourceType,
        source_reference: str | None,
        change_summary: str,
    ) -> BriefBundle:
        self._validate_content(structured_content)
        self._validate_source_reference(source_reference)
        now = self.clock()
        new_version_id = self.id_factory()
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, MUTATION_ROLES, mutable=True)
            current = self._require_brief(uow, context, project_id, brief_id)
            if source_version_id != current.current_version_id:
                raise ResourceConflict(
                    "source version is no longer current", code="version_conflict"
                )
            old_version = self._require_version(
                uow, context, project_id, current, source_version_id
            )
            updated = current.new_version(
                expected_version=expected_brief_version,
                new_version_id=new_version_id,
                now=now,
            )
            result = uow.briefs.update(
                updated,
                expected_version=expected_brief_version,
                expected_current_version_id=expected_current_version_id,
            )
            if old_version.lifecycle_state is not BriefVersionLifecycle.APPROVED:
                uow.brief_versions.supersede(old_version.supersede())
            new_version = self._new_version_entity(
                context,
                project_id,
                brief_id,
                new_version_id,
                version_number=result.latest_version_number,
                structured_content=structured_content,
                source_type=source_type,
                source_reference=source_reference,
                change_summary=change_summary,
                supersedes_version_id=source_version_id,
                now=now,
            )
            saved_version = uow.brief_versions.add(new_version)
            issues = self._add_detected_issues(uow, context, saved_version, now)
            uow.audit_events.append(
                self._event(
                    context,
                    brief_id,
                    "brief.version_created",
                    {
                        "brief_version": saved_version.version_number,
                        "supersedes_version_id": str(source_version_id),
                        "content_schema_version": STRUCTURED_BRIEF_SCHEMA_VERSION,
                        "detected_issue_count": len(issues),
                        "version": result.version,
                    },
                    now,
                )
            )
            return BriefBundle(result, saved_version, issues)

    def submit(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        *,
        expected_brief_version: int,
        expected_current_version_id: UUID,
    ) -> BriefBundle:
        return self._transition(
            context,
            project_id,
            brief_id,
            expected_brief_version=expected_brief_version,
            expected_current_version_id=expected_current_version_id,
            action="brief.submitted_for_review",
            allowed_roles=MUTATION_ROLES,
        )

    def approve(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        *,
        expected_brief_version: int,
        expected_current_version_id: UUID,
    ) -> BriefBundle:
        return self._transition(
            context,
            project_id,
            brief_id,
            expected_brief_version=expected_brief_version,
            expected_current_version_id=expected_current_version_id,
            action="brief.approved",
            allowed_roles=ADMIN_ROLES,
        )

    def archive(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        *,
        expected_brief_version: int,
        expected_current_version_id: UUID,
    ) -> BriefBundle:
        return self._transition(
            context,
            project_id,
            brief_id,
            expected_brief_version=expected_brief_version,
            expected_current_version_id=expected_current_version_id,
            action="brief.archived",
            allowed_roles=ADMIN_ROLES,
        )

    def create_issue(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
        *,
        expected_brief_version: int,
        expected_current_version_id: UUID,
        issue_type: RequirementIssueType,
        field_path: str,
        severity: RequirementIssueSeverity,
        message: str,
    ) -> RequirementIssue:
        now = self.clock()
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, MUTATION_ROLES, mutable=True)
            brief = self._require_brief(uow, context, project_id, brief_id)
            if version_id != brief.current_version_id:
                raise ResourceConflict("issues may only be added to the current version")
            self._require_version(uow, context, project_id, brief, version_id)
            touched = brief.touch(expected_version=expected_brief_version, now=now)
            uow.briefs.update(
                touched,
                expected_version=expected_brief_version,
                expected_current_version_id=expected_current_version_id,
            )
            issue = self._issue(
                context,
                project_id,
                brief_id,
                version_id,
                issue_type,
                field_path,
                severity,
                message,
                now,
            )
            result = uow.requirement_issues.add(issue)
            uow.audit_events.append(
                self._event(
                    context,
                    brief_id,
                    "brief.issue_created",
                    {"issue_id": str(result.id), "brief_version_id": str(version_id)},
                    now,
                )
            )
            return result

    def close_issue(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
        issue_id: UUID,
        *,
        expected_brief_version: int,
        expected_current_version_id: UUID,
        expected_issue_version: int,
        resolution_note: str,
        target_status: RequirementIssueStatus,
    ) -> RequirementIssue:
        if target_status not in {RequirementIssueStatus.RESOLVED, RequirementIssueStatus.DISMISSED}:
            raise InvalidRequest("issue target status is invalid")
        now = self.clock()
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, MUTATION_ROLES, mutable=True)
            brief = self._require_brief(uow, context, project_id, brief_id)
            if version_id != brief.current_version_id:
                raise ResourceConflict("only current-version issues may be changed")
            issue = uow.requirement_issues.get(
                context.organization_id,
                context.workspace_id,
                project_id,
                brief_id,
                version_id,
                issue_id,
            )
            if issue is None:
                raise ResourceNotFound("requirement issue is not accessible")
            touched = brief.touch(expected_version=expected_brief_version, now=now)
            uow.briefs.update(
                touched,
                expected_version=expected_brief_version,
                expected_current_version_id=expected_current_version_id,
            )
            updated = replace(
                issue,
                status=target_status,
                resolution_note=resolution_note,
                resolved_by_actor_subject=context.actor_subject,
                resolved_at=now,
                version=issue.version + 1,
            )
            result = uow.requirement_issues.update(
                updated,
                expected_version=expected_issue_version,
                expected_status=RequirementIssueStatus.OPEN,
            )
            action = (
                "brief.issue_resolved"
                if target_status is RequirementIssueStatus.RESOLVED
                else "brief.issue_dismissed"
            )
            uow.audit_events.append(
                self._event(context, brief_id, action, {"issue_id": str(issue_id)}, now)
            )
            return result

    def _transition(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        *,
        expected_brief_version: int,
        expected_current_version_id: UUID,
        action: str,
        allowed_roles: frozenset[MembershipRole],
    ) -> BriefBundle:
        now = self.clock()
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, allowed_roles, mutable=True)
            current = self._require_brief(uow, context, project_id, brief_id)
            version = self._require_version(
                uow, context, project_id, current, current.current_version_id
            )
            if action == "brief.approved":
                blockers = uow.requirement_issues.count_open_blocking(
                    context.organization_id,
                    context.workspace_id,
                    project_id,
                    brief_id,
                    version.id,
                )
                if blockers:
                    raise ApprovalBlocked("open blocking requirement issues prevent approval")
                updated = current.approve(expected_version=expected_brief_version, now=now)
                next_version = version.approve(actor_subject=context.actor_subject, now=now)
            elif action == "brief.submitted_for_review":
                updated = current.submit(expected_version=expected_brief_version, now=now)
                next_version = version.submit_for_review(now=now)
            else:
                updated = current.archive(expected_version=expected_brief_version, now=now)
                next_version = version
            result = uow.briefs.update(
                updated,
                expected_version=expected_brief_version,
                expected_current_version_id=expected_current_version_id,
            )
            saved_version = version
            if action == "brief.approved":
                saved_version = uow.brief_versions.approve(next_version)
            elif action == "brief.submitted_for_review":
                saved_version = uow.brief_versions.submit_for_review(next_version)
            issues = uow.requirement_issues.list(
                context.organization_id,
                context.workspace_id,
                project_id,
                brief_id,
                version.id,
            )
            uow.audit_events.append(
                self._event(
                    context,
                    brief_id,
                    action,
                    {
                        "brief_version_id": str(version.id),
                        "from_status": current.status.value,
                        "to_status": result.status.value,
                        "version": result.version,
                    },
                    now,
                )
            )
            return BriefBundle(result, saved_version, issues)

    @staticmethod
    def _validate_content(content: dict[str, object]) -> None:
        encoded = json.dumps(content, separators=(",", ":"), ensure_ascii=False).encode()
        if len(encoded) > MAX_STRUCTURED_CONTENT_BYTES:
            raise InvalidRequest("structured Brief content exceeds the size limit")
        try:
            validate_structured_brief(content)
        except ValidationError as error:
            raise InvalidRequest(
                "structured Brief content does not match the canonical schema"
            ) from error

    @staticmethod
    def _validate_source_reference(source_reference: str | None) -> None:
        if source_reference is not None and not SOURCE_REFERENCE_PATTERN.fullmatch(
            source_reference
        ):
            raise InvalidRequest("source_reference must be an opaque identifier")

    def _add_detected_issues(
        self, uow: UnitOfWork, context: TenantContext, version: BriefVersion, now: datetime
    ) -> list[RequirementIssue]:
        issues = []
        for detected in detect_requirement_issues(version.structured_content):
            issue = self._issue(
                context,
                version.project_id,
                version.brief_id,
                version.id,
                detected.issue_type,
                detected.field_path,
                detected.severity,
                detected.message,
                now,
                actor_subject="system:deterministic-checker",
            )
            issues.append(uow.requirement_issues.add(issue))
        return issues

    def _new_version_entity(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
        *,
        version_number: int,
        structured_content: dict[str, object],
        source_type: BriefSourceType,
        source_reference: str | None,
        change_summary: str,
        supersedes_version_id: UUID | None,
        now: datetime,
    ) -> BriefVersion:
        return BriefVersion(
            id=version_id,
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            project_id=project_id,
            brief_id=brief_id,
            version_number=version_number,
            lifecycle_state=BriefVersionLifecycle.DRAFT,
            structured_content=structured_content,
            source_type=source_type,
            source_reference=source_reference,
            change_summary=change_summary,
            created_by_actor_subject=context.actor_subject,
            created_at=now,
            submitted_for_review_at=None,
            approved_at=None,
            approved_by_actor_subject=None,
            supersedes_version_id=supersedes_version_id,
            content_schema_version=STRUCTURED_BRIEF_SCHEMA_VERSION,
        )

    def _issue(
        self,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
        issue_type: RequirementIssueType,
        field_path: str,
        severity: RequirementIssueSeverity,
        message: str,
        now: datetime,
        *,
        actor_subject: str | None = None,
    ) -> RequirementIssue:
        return RequirementIssue(
            id=self.id_factory(),
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            project_id=project_id,
            brief_id=brief_id,
            brief_version_id=version_id,
            issue_type=issue_type,
            field_path=field_path,
            severity=severity,
            message=message,
            status=RequirementIssueStatus.OPEN,
            resolution_note=None,
            created_by_actor_subject=actor_subject or context.actor_subject,
            resolved_by_actor_subject=None,
            created_at=now,
            resolved_at=None,
            version=1,
        )

    @staticmethod
    def _require_project_access(
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        roles: frozenset[MembershipRole],
        *,
        mutable: bool = False,
    ) -> Project:
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
            or membership.role not in roles
            or project is None
        ):
            raise ResourceNotFound("project is not accessible")
        if mutable and project.status is ProjectStatus.ARCHIVED:
            raise ResourceConflict("archived projects cannot be changed", code="project_archived")
        return project

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
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        brief: Brief,
        version_id: UUID,
    ) -> BriefVersion:
        version = uow.brief_versions.get(
            context.organization_id,
            context.workspace_id,
            project_id,
            brief.id,
            version_id,
        )
        if version is None:
            raise ResourceNotFound("brief version is not accessible")
        return version

    def _event(
        self,
        context: TenantContext,
        brief_id: UUID,
        action: str,
        payload: dict[str, object],
        occurred_at: datetime,
    ) -> AuditEvent:
        return AuditEvent(
            id=self.id_factory(),
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            actor_subject=context.actor_subject,
            aggregate_type="brief",
            aggregate_id=brief_id,
            action=action,
            payload=payload,
            occurred_at=occurred_at,
            correlation_id=context.correlation_id,
        )
