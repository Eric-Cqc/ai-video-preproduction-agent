import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text

from infra.scripts.reset_test_database import require_test_database_url
from services.api.app.application.brief_services import BriefApplicationService, BriefBundle
from services.api.app.application.context import ActorContext, OrganizationContext, TenantContext
from services.api.app.application.errors import ResourceConflict, ResourceNotFound
from services.api.app.application.repositories import AuditEventRepository
from services.api.app.application.services import TenantApplicationService
from services.api.app.domain import (
    AuditEvent,
    BriefSourceType,
    Membership,
    MembershipRole,
    MembershipStatus,
    Project,
    ProjectStatus,
    RequirementIssue,
    RequirementIssueSeverity,
    RequirementIssueStatus,
    RequirementIssueType,
    VersionConflict,
)
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork


def actor(subject: str = "actor:owner") -> ActorContext:
    return ActorContext(actor_subject=subject, correlation_id=str(uuid4()))


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://foundation:foundation@localhost/foundation_local",
        "postgresql+psycopg://foundation:foundation@localhost/foundation_local?label=_test",
        "sqlite:///foundation_test",
    ],
)
def test_database_safety_guard_parses_the_real_database_name(database_url: str) -> None:
    with pytest.raises(RuntimeError):
        require_test_database_url(database_url)

    assert require_test_database_url(
        "postgresql+psycopg://foundation:foundation@localhost/foundation_test"
    ).endswith("foundation_test")


def bootstrap(
    service: TenantApplicationService,
) -> tuple[OrganizationContext, TenantContext]:
    owner = actor()
    organization = service.create_organization(owner, slug="example-org", name="Example Org")
    org_context = OrganizationContext(
        actor_subject=owner.actor_subject,
        correlation_id=owner.correlation_id,
        organization_id=organization.id,
    )
    workspace = service.create_workspace(org_context, slug="main", name="Main Workspace")
    return org_context, TenantContext(
        actor_subject=owner.actor_subject,
        correlation_id=owner.correlation_id,
        organization_id=organization.id,
        workspace_id=workspace.id,
    )


def test_organization_workspace_membership_and_project_persist(
    persistence_service: TenantApplicationService,
) -> None:
    _, context = bootstrap(persistence_service)
    membership = persistence_service.create_membership(
        context, actor_subject="actor:member", role=MembershipRole.MEMBER
    )
    project = persistence_service.create_project(
        context, name="Tenant Foundation", description=None
    )
    loaded = persistence_service.get_project(context, project.id)
    assert membership.workspace_id == context.workspace_id
    assert loaded == project
    assert loaded.status is ProjectStatus.DRAFT


def test_unique_slug_and_partial_membership_indexes_are_enforced(
    persistence_service: TenantApplicationService,
) -> None:
    org_context, context = bootstrap(persistence_service)
    with pytest.raises(ResourceConflict) as organization_conflict:
        persistence_service.create_organization(
            actor("actor:other"), slug="example-org", name="Other"
        )
    assert organization_conflict.value.code == "organization_slug_conflict"

    with pytest.raises(ResourceConflict) as workspace_conflict:
        persistence_service.create_workspace(org_context, slug="main", name="Duplicate")
    assert workspace_conflict.value.code == "workspace_slug_conflict"

    persistence_service.create_membership(
        context, actor_subject="actor:member", role=MembershipRole.MEMBER
    )
    with pytest.raises(ResourceConflict) as membership_conflict:
        persistence_service.create_membership(
            context, actor_subject="actor:member", role=MembershipRole.VIEWER
        )
    assert membership_conflict.value.code == "membership_conflict"


def test_cross_organization_workspace_reference_is_hidden_by_application(
    persistence_service: TenantApplicationService,
) -> None:
    _, context_a = bootstrap(persistence_service)
    owner_b = actor("actor:b")
    org_b = persistence_service.create_organization(owner_b, slug="org-b", name="Org B")
    mismatched = TenantContext(
        actor_subject=context_a.actor_subject,
        correlation_id=context_a.correlation_id,
        organization_id=org_b.id,
        workspace_id=context_a.workspace_id,
    )
    with pytest.raises(ResourceNotFound):
        persistence_service.create_project(mismatched, name="Invalid", description=None)


class FailingAuditRepository(AuditEventRepository):
    def append(self, event: AuditEvent) -> AuditEvent:
        del event
        raise RuntimeError("simulated audit failure")

    def list_for_project(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID
    ) -> list[AuditEvent]:
        del organization_id, workspace_id, project_id
        return []

    def list_for_brief(
        self, organization_id: UUID, workspace_id: UUID, brief_id: UUID
    ) -> list[AuditEvent]:
        del organization_id, workspace_id, brief_id
        return []


class FailingAuditUnitOfWork(SqlAlchemyUnitOfWork):
    def __enter__(self) -> "FailingAuditUnitOfWork":
        super().__enter__()
        self.audit_events = FailingAuditRepository()
        return self


def test_failed_audit_write_rolls_back_project_creation(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
) -> None:
    del clean_database
    normal_service = TenantApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    _, context = bootstrap(normal_service)
    failing_service = TenantApplicationService(
        lambda: FailingAuditUnitOfWork(persistence_session_factory)
    )
    with pytest.raises(RuntimeError, match="simulated audit failure"):
        failing_service.create_project(context, name="Rolled Back", description=None)

    with database_engine.connect() as connection:
        count = connection.scalar(text("SELECT count(*) FROM projects"))
    assert count == 0


def test_failed_audit_write_rolls_back_brief_and_initial_version(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
) -> None:
    del clean_database
    normal_service = TenantApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    _, context = bootstrap(normal_service)
    project = normal_service.create_project(context, name="Brief Project", description=None)
    failing_service = BriefApplicationService(
        lambda: FailingAuditUnitOfWork(persistence_session_factory)
    )
    fixture_path = (
        Path(__file__).resolve().parents[3]
        / "packages/test-fixtures/brief/valid-structured-brief-v1.json"
    )
    content = json.loads(fixture_path.read_text())

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        failing_service.create_brief(
            context,
            project.id,
            title="Rolled Back Brief",
            structured_content=content,
            source_type=BriefSourceType.MANUAL,
            source_reference=None,
            change_summary="Must roll back",
        )

    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM briefs), "
                "(SELECT count(*) FROM brief_versions), "
                "(SELECT count(*) FROM requirement_issues)"
            )
        ).one()
    assert counts == (0, 0, 0)


def _brief_content() -> dict[str, object]:
    fixture_path = (
        Path(__file__).resolve().parents[3]
        / "packages/test-fixtures/brief/valid-structured-brief-v1.json"
    )
    return cast(dict[str, object], json.loads(fixture_path.read_text()))


def _create_brief(
    service: BriefApplicationService, context: TenantContext, project_id: UUID
) -> BriefBundle:
    return service.create_brief(
        context,
        project_id,
        title="Persistence Brief",
        structured_content=_brief_content(),
        source_type=BriefSourceType.MANUAL,
        source_reference=None,
        change_summary="Initial snapshot",
    )


def _create_approved_brief(
    service: BriefApplicationService, context: TenantContext, project_id: UUID
) -> BriefBundle:
    created = _create_brief(service, context, project_id)
    submitted = service.submit(
        context,
        project_id,
        created.brief.id,
        expected_brief_version=created.brief.version,
        expected_current_version_id=created.brief.current_version_id,
    )
    return service.approve(
        context,
        project_id,
        submitted.brief.id,
        expected_brief_version=submitted.brief.version,
        expected_current_version_id=submitted.brief.current_version_id,
    )


def test_failed_audit_write_rolls_back_new_version_and_pointer_move(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
) -> None:
    del clean_database
    tenant_service = TenantApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    _, context = bootstrap(tenant_service)
    project = tenant_service.create_project(context, name="Brief Project", description=None)
    normal_brief_service = BriefApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    approved = _create_approved_brief(normal_brief_service, context, project.id)
    before = normal_brief_service.get_brief(context, project.id, approved.brief.id)
    failing_service = BriefApplicationService(
        lambda: FailingAuditUnitOfWork(persistence_session_factory)
    )

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        failing_service.create_version(
            context,
            before.brief.project_id,
            before.brief.id,
            expected_brief_version=before.brief.version,
            expected_current_version_id=before.brief.current_version_id,
            source_version_id=before.current_version.id,
            structured_content=_brief_content(),
            source_type=BriefSourceType.MANUAL,
            source_reference=None,
            change_summary="Must roll back pointer and successor",
        )

    after = normal_brief_service.get_brief(context, project.id, approved.brief.id)
    assert after == before
    assert normal_brief_service.list_versions(context, project.id, approved.brief.id) == [
        before.current_version
    ]
    with pytest.raises(VersionConflict), uow_factory() as uow:
        approved_version = uow.brief_versions.get(
            context.organization_id,
            context.workspace_id,
            project.id,
            approved.brief.id,
            before.current_version.id,
        )
        assert approved_version is not None
        uow.brief_versions.supersede(approved_version)


def test_brief_version_and_issue_composite_foreign_keys_reject_cross_brief_tenant_rows(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
) -> None:
    del clean_database
    tenant_service = TenantApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    _, context_a = bootstrap(tenant_service)
    project_a = tenant_service.create_project(context_a, name="Project A", description=None)
    owner_b = actor("actor:b")
    organization_b = tenant_service.create_organization(owner_b, slug="org-b", name="Org B")
    context_b_organization = OrganizationContext(
        actor_subject=owner_b.actor_subject,
        correlation_id=owner_b.correlation_id,
        organization_id=organization_b.id,
    )
    workspace_b = tenant_service.create_workspace(context_b_organization, slug="main", name="Main")
    context_b = TenantContext(
        actor_subject=owner_b.actor_subject,
        correlation_id=owner_b.correlation_id,
        organization_id=organization_b.id,
        workspace_id=workspace_b.id,
    )
    project_b = tenant_service.create_project(context_b, name="Project B", description=None)
    brief_service = BriefApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    brief_a = _create_brief(brief_service, context_a, project_a.id)
    brief_b = _create_brief(brief_service, context_b, project_b.id)

    invalid_successor = replace(
        brief_a.current_version,
        id=uuid4(),
        version_number=2,
        supersedes_version_id=brief_b.current_version.id,
    )
    with pytest.raises(ResourceConflict), uow_factory() as uow:
        uow.brief_versions.add(invalid_successor)

    invalid_issue = RequirementIssue(
        id=uuid4(),
        organization_id=context_a.organization_id,
        workspace_id=context_a.workspace_id,
        project_id=project_a.id,
        brief_id=brief_a.brief.id,
        brief_version_id=brief_b.current_version.id,
        issue_type=RequirementIssueType.MISSING,
        field_path="objective.primary_goal",
        severity=RequirementIssueSeverity.BLOCKING,
        message="Invalid cross-tenant version reference",
        status=RequirementIssueStatus.OPEN,
        resolution_note=None,
        created_by_actor_subject=context_a.actor_subject,
        resolved_by_actor_subject=None,
        created_at=datetime.now(UTC),
        resolved_at=None,
        version=1,
    )
    with pytest.raises(ResourceConflict), uow_factory() as uow:
        uow.requirement_issues.add(invalid_issue)


def test_stale_mutation_does_not_overwrite_or_append_audit(
    persistence_service: TenantApplicationService,
) -> None:
    _, context = bootstrap(persistence_service)
    project = persistence_service.create_project(context, name="Original", description=None)
    updated = persistence_service.update_project(
        context,
        project.id,
        expected_version=1,
        changed_fields=frozenset({"name"}),
        name="Updated",
        description=None,
    )
    before_events = persistence_service.list_project_audit_events(context, project.id)

    with pytest.raises(VersionConflict):
        persistence_service.update_project(
            context,
            project.id,
            expected_version=1,
            changed_fields=frozenset({"name"}),
            name="Stale overwrite",
            description=None,
        )
    current = persistence_service.get_project(context, project.id)
    after_events = persistence_service.list_project_audit_events(context, project.id)
    assert current.name == "Updated"
    assert current.version == updated.version == 2
    assert len(after_events) == len(before_events)


def test_composite_tenant_foreign_keys_reject_mismatched_ownership(
    persistence_service: TenantApplicationService,
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
) -> None:
    _, context_a = bootstrap(persistence_service)
    owner_b = actor("actor:b")
    organization_b = persistence_service.create_organization(owner_b, slug="org-b", name="Org B")
    now = datetime.now(UTC)

    mismatched_project = Project(
        id=uuid4(),
        organization_id=organization_b.id,
        workspace_id=context_a.workspace_id,
        name="Invalid",
        description=None,
        status=ProjectStatus.DRAFT,
        created_by_actor_subject=owner_b.actor_subject,
        created_at=now,
        updated_at=now,
        version=1,
    )
    with pytest.raises(ResourceConflict), uow_factory() as uow:
        uow.projects.add(mismatched_project)

    mismatched_membership = Membership(
        id=uuid4(),
        organization_id=organization_b.id,
        workspace_id=context_a.workspace_id,
        actor_subject="actor:invalid",
        role=MembershipRole.MEMBER,
        status=MembershipStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        version=1,
    )
    with pytest.raises(ResourceConflict), uow_factory() as uow:
        uow.memberships.add(mismatched_membership)

    mismatched_audit = AuditEvent(
        id=uuid4(),
        organization_id=organization_b.id,
        workspace_id=context_a.workspace_id,
        actor_subject=owner_b.actor_subject,
        aggregate_type="project",
        aggregate_id=uuid4(),
        action="project.created",
        payload={"version": 1},
        occurred_at=now,
        correlation_id=owner_b.correlation_id,
    )
    with pytest.raises(ResourceConflict), uow_factory() as uow:
        uow.audit_events.append(mismatched_audit)
