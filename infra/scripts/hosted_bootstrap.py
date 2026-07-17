from collections.abc import Iterator
from uuid import UUID, uuid4

from services.api.app.application.context import ActorContext, OrganizationContext
from services.api.app.application.services import TenantApplicationService
from services.api.app.config import get_api_settings
from services.api.app.infrastructure.database import create_database_engine, create_session_factory
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork


def _id_factory(values: Iterator[UUID]) -> UUID:
    return next(values, uuid4)


def main() -> None:
    settings = get_api_settings()
    if not settings.hosted_pilot_enabled:
        raise SystemExit("hosted bootstrap requires APP_ENVIRONMENT=hosted")
    organization_id = settings.pilot_organization_id
    workspace_id = settings.pilot_workspace_id
    actor = settings.pilot_actor_subject
    if organization_id is None or workspace_id is None or actor is None:
        raise SystemExit("hosted pilot configuration is incomplete")
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    try:
        with SqlAlchemyUnitOfWork(factory) as uow:
            organization = uow.organizations.get(organization_id)
            workspace = uow.workspaces.get(organization_id, workspace_id)
        ids = iter((organization_id, uuid4(), workspace_id))
        service = TenantApplicationService(
            lambda: SqlAlchemyUnitOfWork(factory), id_factory=lambda: _id_factory(ids)
        )
        actor_context = ActorContext(actor, "hosted-bootstrap")
        if organization is None:
            organization = service.create_organization(
                actor_context,
                slug=settings.pilot_organization_slug,
                name=settings.pilot_organization_name,
            )
        elif (
            organization.slug != settings.pilot_organization_slug
            or organization.name != settings.pilot_organization_name
        ):
            raise SystemExit("configured pilot Organization conflicts with persisted Organization")
        if workspace is None:
            workspace = service.create_workspace(
                OrganizationContext(actor, "hosted-bootstrap", organization.id),
                slug=settings.pilot_workspace_slug,
                name=settings.pilot_workspace_name,
            )
        elif (
            workspace.slug != settings.pilot_workspace_slug
            or workspace.name != settings.pilot_workspace_name
        ):
            raise SystemExit("configured pilot Workspace conflicts with persisted Workspace")
        print(f"Hosted pilot ready: organization={organization.id} workspace={workspace.id}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
