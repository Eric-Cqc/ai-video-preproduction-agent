from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict
from uuid import UUID, uuid4

from foundation_contracts import STRUCTURED_BRIEF_SCHEMA_VERSION, validate_structured_brief
from jsonschema import ValidationError

from services.api.app.application.context import TenantContext
from services.api.app.application.errors import InvalidRequest, ResourceConflict, ResourceNotFound
from services.api.app.application.model_provider import (
    ModelProviderPort,
    ModelRequest,
    ProviderOutcomeStatus,
)
from services.api.app.application.services import MUTATION_ROLES, Clock, IdFactory, utc_now
from services.api.app.application.uow import UnitOfWork
from services.api.app.domain import (
    AuditEvent,
    Brief,
    BriefSourceType,
    BriefStatus,
    BriefVersion,
    BriefVersionLifecycle,
    IdeaIntake,
    IdeaIntakeStatus,
    Membership,
    OrganizationStatus,
    Project,
    ProjectStatus,
    RequirementIssue,
    RequirementIssueStatus,
    WorkspaceStatus,
)
from services.api.app.domain.brief_issues import detect_requirement_issues

UnitOfWorkFactory = Callable[[], UnitOfWork]
PROMPT_TEMPLATE_ID = "idea_intake_structuring"
PROMPT_TEMPLATE_VERSION = "1.0.0"
MAX_RAW_IDEA_CHARACTERS = 8_000
MAX_MODEL_OUTPUT_CHARACTERS = 16_384
MAX_STRUCTURE_ATTEMPTS = 2

IDEA_INTAKE_PROMPT = (
    "Return exactly one JSON object and nothing else. Structure the user's production idea "
    "for a video preproduction brief. Never invent business facts: unknown values must be null. "
    "Return at most three missing_fields. Always record assumptions, even if empty. "
    'Use this exact shape: {"objective":null,"platform":null,"audience":null,'
    '"duration_seconds":null,"content_type":null,"tone":[],"key_messages":[],'
    '"call_to_action":null,"constraints":[],"must_include":[],"must_avoid":[],'
    '"assumptions":[],"missing_fields":[]}. Do not browse, use tools, fetch URLs, '
    "generate scripts, storyboards, shot plans, images, video, or media."
)


@dataclass(frozen=True, slots=True)
class IdeaIntakeConfirmation:
    intake: IdeaIntake
    brief: Brief
    current_version: BriefVersion
    issues: list[RequirementIssue]


class StructuredIdeaFields(TypedDict):
    objective: str | None
    platform: str | None
    audience: str | None
    duration_seconds: int | None
    content_type: str | None
    tone: list[str]
    key_messages: list[str]
    call_to_action: str | None
    constraints: list[str]
    must_include: list[str]
    must_avoid: list[str]
    assumptions: list[str]
    missing_fields: list[str]


class IdeaIntakeApplicationService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        provider: ModelProviderPort,
        *,
        clock: Clock = utc_now,
        id_factory: IdFactory = uuid4,
    ) -> None:
        self.uow_factory = uow_factory
        self.provider = provider
        self.clock = clock
        self.id_factory = id_factory

    def create(self, context: TenantContext, project_id: UUID, *, raw_idea: str) -> IdeaIntake:
        idea = _validate_raw_idea(raw_idea)
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, mutable=True)
        structured = self._structure_idea(idea)
        now = self.clock()
        intake = IdeaIntake(
            id=self.id_factory(),
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            project_id=project_id,
            raw_idea=idea,
            status=IdeaIntakeStatus.STRUCTURED,
            brief_id=None,
            brief_version_id=None,
            created_by_actor_subject=context.actor_subject,
            created_at=now,
            updated_at=now,
            version=1,
            **structured,
        )
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, mutable=True)
            result = uow.idea_intakes.add(intake)
            uow.audit_events.append(
                self._event(
                    context,
                    result,
                    "idea_intake.structured",
                    {
                        "version": 1,
                        "missing_field_count": len(result.missing_fields),
                        "assumption_count": len(result.assumptions),
                        "provider_id": self.provider.provider_id,
                        "model_id": self.provider.model_id,
                    },
                    now,
                )
            )
            return result

    def get(self, context: TenantContext, project_id: UUID, intake_id: UUID) -> IdeaIntake:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id)
            intake = uow.idea_intakes.get(
                context.organization_id, context.workspace_id, project_id, intake_id
            )
            if intake is None:
                raise ResourceNotFound("idea intake is not accessible")
            return intake

    def list_intakes(self, context: TenantContext, project_id: UUID) -> list[IdeaIntake]:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id)
            return uow.idea_intakes.list(context.organization_id, context.workspace_id, project_id)

    def update(
        self,
        context: TenantContext,
        project_id: UUID,
        intake_id: UUID,
        *,
        expected_version: int,
        objective: str | None,
        platform: str | None,
        audience: str | None,
        duration_seconds: int | None,
        content_type: str | None,
        tone: list[str],
        key_messages: list[str],
        call_to_action: str | None,
        constraints: list[str],
        must_include: list[str],
        must_avoid: list[str],
        assumptions: list[str],
        missing_fields: list[str],
    ) -> IdeaIntake:
        now = self.clock()
        structured = _validated_structured_fields(
            {
                "objective": objective,
                "platform": platform,
                "audience": audience,
                "duration_seconds": duration_seconds,
                "content_type": content_type,
                "tone": tone,
                "key_messages": key_messages,
                "call_to_action": call_to_action,
                "constraints": constraints,
                "must_include": must_include,
                "must_avoid": must_avoid,
                "assumptions": assumptions,
                "missing_fields": missing_fields,
            }
        )
        # A saved answer resolves its field gap; other questions and assumptions remain.
        resolved_fields = {
            field
            for field, value in structured.items()
            if field not in {"assumptions", "missing_fields"} and value
        }
        structured["missing_fields"] = [
            field for field in structured["missing_fields"] if field not in resolved_fields
        ]
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, mutable=True)
            current = self._require_intake(uow, context, project_id, intake_id)
            updated = current.patch(expected_version=expected_version, now=now, **structured)
            result = uow.idea_intakes.update(updated, expected_version=expected_version)
            uow.audit_events.append(
                self._event(
                    context,
                    result,
                    "idea_intake.updated",
                    {
                        "version": result.version,
                        "missing_field_count": len(result.missing_fields),
                        "assumption_count": len(result.assumptions),
                    },
                    now,
                )
            )
            return result

    def confirm(
        self,
        context: TenantContext,
        project_id: UUID,
        intake_id: UUID,
        *,
        expected_version: int,
        title: str | None = None,
    ) -> IdeaIntakeConfirmation:
        now = self.clock()
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, mutable=True)
            current = self._require_intake(uow, context, project_id, intake_id)
            if current.status is IdeaIntakeStatus.CONFIRMED:
                raise ResourceConflict("idea intake is already confirmed", code="idea_confirmed")
            content = _structured_brief_from_intake(current)
            try:
                validate_structured_brief(content)
            except ValidationError as error:
                raise InvalidRequest(
                    "idea intake cannot be converted to a canonical Structured Brief",
                    code="idea_intake_invalid",
                ) from error
            brief_id = self.id_factory()
            version_id = self.id_factory()
            brief = Brief(
                id=brief_id,
                organization_id=context.organization_id,
                workspace_id=context.workspace_id,
                project_id=project_id,
                title=_brief_title(title, current),
                status=BriefStatus.DRAFT,
                current_version_id=version_id,
                latest_version_number=1,
                created_by_actor_subject=context.actor_subject,
                created_at=now,
                updated_at=now,
                version=1,
            )
            version = BriefVersion(
                id=version_id,
                organization_id=context.organization_id,
                workspace_id=context.workspace_id,
                project_id=project_id,
                brief_id=brief_id,
                version_number=1,
                lifecycle_state=BriefVersionLifecycle.DRAFT,
                structured_content=content,
                source_type=BriefSourceType.IDEA_INTAKE,
                source_reference=str(current.id),
                change_summary="Created from confirmed Idea Intake.",
                created_by_actor_subject=context.actor_subject,
                created_at=now,
                submitted_for_review_at=None,
                approved_at=None,
                approved_by_actor_subject=None,
                supersedes_version_id=None,
                content_schema_version=STRUCTURED_BRIEF_SCHEMA_VERSION,
            )
            saved_brief = uow.briefs.add(brief)
            saved_version = uow.brief_versions.add(version)
            issues = self._add_detected_issues(uow, context, saved_version, now)
            confirmed = current.confirm(
                expected_version=expected_version,
                brief_id=saved_brief.id,
                brief_version_id=saved_version.id,
                now=now,
            )
            saved_intake = uow.idea_intakes.confirm(
                confirmed,
                expected_version=expected_version,
                expected_status=IdeaIntakeStatus.STRUCTURED,
            )
            uow.audit_events.append(
                self._event(
                    context,
                    saved_intake,
                    "idea_intake.confirmed",
                    {
                        "version": saved_intake.version,
                        "brief_id": str(saved_brief.id),
                        "brief_version_id": str(saved_version.id),
                        "detected_issue_count": len(issues),
                    },
                    now,
                )
            )
            uow.audit_events.append(
                AuditEvent(
                    id=self.id_factory(),
                    organization_id=context.organization_id,
                    workspace_id=context.workspace_id,
                    actor_subject=context.actor_subject,
                    aggregate_type="brief",
                    aggregate_id=saved_brief.id,
                    action="brief.created",
                    payload={
                        "brief_version": 1,
                        "content_schema_version": STRUCTURED_BRIEF_SCHEMA_VERSION,
                        "detected_issue_count": len(issues),
                        "source_type": BriefSourceType.IDEA_INTAKE.value,
                        "version": 1,
                    },
                    occurred_at=now,
                    correlation_id=context.correlation_id,
                )
            )
            return IdeaIntakeConfirmation(saved_intake, saved_brief, saved_version, issues)

    def _structure_idea(self, raw_idea: str) -> StructuredIdeaFields:
        last_error: InvalidRequest | None = None
        for _ in range(MAX_STRUCTURE_ATTEMPTS):
            outcome = self.provider.complete(
                ModelRequest(
                    instruction_template_id=PROMPT_TEMPLATE_ID,
                    instruction_template_version=PROMPT_TEMPLATE_VERSION,
                    instructions=IDEA_INTAKE_PROMPT,
                    input_text=raw_idea,
                    max_output_characters=MAX_MODEL_OUTPUT_CHARACTERS,
                    allow_tools=False,
                )
            )
            if outcome.status is ProviderOutcomeStatus.REFUSAL:
                raise InvalidRequest(
                    "idea intake provider refused the request", code="provider_refusal"
                )
            if outcome.status is ProviderOutcomeStatus.TIMEOUT:
                raise InvalidRequest("idea intake provider timed out", code="provider_timeout")
            if outcome.status is not ProviderOutcomeStatus.SUCCESS:
                raise InvalidRequest("idea intake provider failed", code="provider_error")
            try:
                return _parse_structured_output(outcome.output_text)
            except InvalidRequest as error:
                last_error = error
        if last_error is None:
            raise InvalidRequest("idea intake provider failed", code="provider_error")
        raise last_error

    def _add_detected_issues(
        self, uow: UnitOfWork, context: TenantContext, version: BriefVersion, now: datetime
    ) -> list[RequirementIssue]:
        issues = []
        for detected in detect_requirement_issues(version.structured_content):
            issue = RequirementIssue(
                id=self.id_factory(),
                organization_id=context.organization_id,
                workspace_id=context.workspace_id,
                project_id=version.project_id,
                brief_id=version.brief_id,
                brief_version_id=version.id,
                issue_type=detected.issue_type,
                field_path=detected.field_path,
                severity=detected.severity,
                message=detected.message,
                status=RequirementIssueStatus.OPEN,
                resolution_note=None,
                created_by_actor_subject="system:deterministic-checker",
                resolved_by_actor_subject=None,
                created_at=now,
                resolved_at=None,
                version=1,
            )
            issues.append(uow.requirement_issues.add(issue))
        return issues

    @staticmethod
    def _require_project_access(
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
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
            or membership.role not in MUTATION_ROLES
            or project is None
        ):
            raise ResourceNotFound("project is not accessible")
        if mutable and project.status is ProjectStatus.ARCHIVED:
            raise ResourceConflict("archived projects cannot be changed", code="project_archived")
        return project

    @staticmethod
    def _require_intake(
        uow: UnitOfWork, context: TenantContext, project_id: UUID, intake_id: UUID
    ) -> IdeaIntake:
        intake = uow.idea_intakes.get(
            context.organization_id, context.workspace_id, project_id, intake_id
        )
        if intake is None:
            raise ResourceNotFound("idea intake is not accessible")
        return intake

    def _event(
        self,
        context: TenantContext,
        intake: IdeaIntake,
        action: str,
        payload: dict[str, object],
        occurred_at: datetime,
    ) -> AuditEvent:
        return AuditEvent(
            id=self.id_factory(),
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            actor_subject=context.actor_subject,
            aggregate_type="idea_intake",
            aggregate_id=intake.id,
            action=action,
            payload=payload,
            occurred_at=occurred_at,
            correlation_id=context.correlation_id,
        )


def _validate_raw_idea(raw_idea: str) -> str:
    value = raw_idea.strip()
    if not value:
        raise InvalidRequest("idea must not be empty")
    if len(value) > MAX_RAW_IDEA_CHARACTERS:
        raise InvalidRequest("idea exceeds the size limit")
    return value


def _parse_structured_output(output_text: str | None) -> StructuredIdeaFields:
    if output_text is None or len(output_text) > MAX_MODEL_OUTPUT_CHARACTERS:
        raise InvalidRequest("idea provider output is malformed", code="malformed_output")
    try:
        value = json.loads(output_text)
    except json.JSONDecodeError as error:
        raise InvalidRequest(
            "idea provider output is malformed", code="malformed_output"
        ) from error
    if not isinstance(value, dict):
        raise InvalidRequest("idea provider output is schema invalid", code="schema_invalid")
    return _validated_structured_fields(value)


def _validated_structured_fields(value: dict[str, object]) -> StructuredIdeaFields:
    expected = {
        "objective",
        "platform",
        "audience",
        "duration_seconds",
        "content_type",
        "tone",
        "key_messages",
        "call_to_action",
        "constraints",
        "must_include",
        "must_avoid",
        "assumptions",
        "missing_fields",
    }
    if set(value) != expected:
        raise InvalidRequest("idea provider output is schema invalid", code="schema_invalid")
    duration = value["duration_seconds"]
    if duration is None:
        duration_seconds = None
    elif isinstance(duration, int) and not isinstance(duration, bool) and 15 <= duration <= 60:
        duration_seconds = duration
    else:
        raise InvalidRequest("idea duration is invalid", code="schema_invalid")
    missing_fields = _bounded_string_list(value["missing_fields"], "missing_fields", 3)
    key_messages = _bounded_string_list(value["key_messages"], "key_messages", 20)
    if len("; ".join(key_messages)) > 1000:
        raise InvalidRequest(
            "key_messages exceed the canonical Brief text limit", code="schema_invalid"
        )
    return {
        "objective": _nullable_string(value["objective"], "objective", 500),
        "platform": _nullable_string(value["platform"], "platform", 120),
        "audience": _nullable_string(value["audience"], "audience", 500),
        "duration_seconds": duration_seconds,
        "content_type": _nullable_string(value["content_type"], "content_type", 120),
        "tone": _bounded_string_list(value["tone"], "tone", 10),
        "key_messages": key_messages,
        "call_to_action": _nullable_string(value["call_to_action"], "call_to_action", 500),
        "constraints": _bounded_string_list(value["constraints"], "constraints", 20),
        "must_include": _bounded_string_list(value["must_include"], "must_include", 20),
        "must_avoid": _bounded_string_list(value["must_avoid"], "must_avoid", 20),
        "assumptions": _bounded_string_list(value["assumptions"], "assumptions", 20),
        "missing_fields": missing_fields,
    }


def _nullable_string(value: object, field: str, max_length: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidRequest(f"{field} must be a string or null", code="schema_invalid")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > max_length:
        raise InvalidRequest(f"{field} is invalid", code="schema_invalid")
    return cleaned


def _bounded_string_list(value: object, field: str, max_items: int) -> list[str]:
    if not isinstance(value, list) or len(value) > max_items:
        raise InvalidRequest(f"{field} must be a bounded string array", code="schema_invalid")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise InvalidRequest(f"{field} must contain only strings", code="schema_invalid")
        cleaned = item.strip()
        if not cleaned or len(cleaned) > 500:
            raise InvalidRequest(f"{field} contains an invalid value", code="schema_invalid")
        result.append(cleaned)
    return list(dict.fromkeys(result))


def _brief_title(title: str | None, intake: IdeaIntake) -> str:
    candidate = (title or intake.objective or "Idea Intake Brief").strip()
    if not candidate:
        candidate = "Idea Intake Brief"
    return candidate[:200]


def _structured_brief_from_intake(intake: IdeaIntake) -> dict[str, object]:
    duration = intake.duration_seconds or 30
    objective = intake.objective or "Clarify the video objective from the submitted idea."
    audience = intake.audience or "Audience to be confirmed"
    platform = intake.platform or "social"
    content_type = intake.content_type or "social video"
    key_messages = list(dict.fromkeys(intake.key_messages)) or ["Message to be confirmed"]
    call_to_action = intake.call_to_action or "Call to action to be confirmed"
    return {
        "schema_version": "1.0.0",
        "objective": {
            "primary_goal": objective,
            "secondary_goals": [],
            "desired_action": call_to_action,
        },
        "audience": {
            "primary_audience": audience,
            "secondary_audiences": [],
            "geography": [],
            "language": [],
            "audience_insights": [],
        },
        "offer": {"offer_details": None, "mandatory_claims": [], "prohibited_claims": []},
        "product": {
            "product_name": None,
            "product_category": content_type,
            "key_features": [],
            "key_benefits": [],
            "proof_points": [],
        },
        "brand": {
            "brand_name": None,
            "tone": list(dict.fromkeys(intake.tone)),
            "personality": [],
            "visual_guidelines": [],
            "mandatory_elements": list(dict.fromkeys(intake.must_include)),
            "prohibited_elements": list(dict.fromkeys(intake.must_avoid)),
        },
        "channels": [_channel_from_platform(platform)],
        "deliverables": {
            "aspect_ratios": ["9:16"]
            if "tiktok" in platform.lower() or "xiaohongshu" in platform.lower()
            else [],
            "duration_seconds": [duration],
            "deliverable_count": 1,
            "locale_variants": [],
            "caption_requirements": None,
            "audio_requirements": None,
        },
        "creative_constraints": {
            "required_message": "; ".join(key_messages),
            "call_to_action": call_to_action,
            "opening_hook_requirements": [],
            "narrative_preferences": list(dict.fromkeys(intake.constraints)),
            "reference_styles": [],
            "prohibited_themes": list(dict.fromkeys(intake.must_avoid)),
        },
        "production_constraints": {
            "available_assets": [],
            "required_assets": [],
            "talent_constraints": [],
            "location_constraints": [],
            "deadline": None,
            "budget_range": {"currency": None, "minimum": None, "maximum": None},
            "model_or_tool_constraints": [],
        },
        "legal_and_compliance": {
            "disclaimer_requirements": [],
            "regulated_category": None,
            "claim_substantiation_notes": [],
            "usage_rights_notes": None,
        },
        "references": [],
        "success_criteria": {
            "business_metrics": [],
            "creative_metrics": [],
            "evaluation_notes": None,
        },
        "open_questions": list(dict.fromkeys(intake.missing_fields)),
    }


def _channel_from_platform(platform: str) -> str:
    lowered = platform.lower()
    if any(token in lowered for token in ("tiktok", "xiaohongshu", "instagram", "social")):
        return "social"
    if "ad" in lowered or "paid" in lowered:
        return "digital_ad"
    return "other"
