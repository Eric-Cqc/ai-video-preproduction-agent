from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ActorContext:
    actor_subject: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class OrganizationContext(ActorContext):
    organization_id: UUID


@dataclass(frozen=True, slots=True)
class TenantContext(OrganizationContext):
    workspace_id: UUID
