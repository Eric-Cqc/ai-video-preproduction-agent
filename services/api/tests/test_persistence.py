from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text

from infra.scripts.reset_test_database import require_test_database_url
from services.api.app.application.context import ActorContext, OrganizationContext, TenantContext
from services.api.app.application.errors import ResourceConflict, ResourceNotFound
from services.api.app.application.repositories import AuditEventRepository
from services.api.app.application.services import TenantApplicationService
from services.api.app.domain import (
    AuditEvent,
    Membership,
    MembershipRole,
    MembershipStatus,
    Project,
    ProjectStatus,
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
