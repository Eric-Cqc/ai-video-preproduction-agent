from dataclasses import dataclass

from services.api.app.domain.brief import RequirementIssueSeverity, RequirementIssueType


@dataclass(frozen=True, slots=True)
class DetectedIssue:
    issue_type: RequirementIssueType
    field_path: str
    severity: RequirementIssueSeverity
    message: str


def detect_requirement_issues(content: dict[str, object]) -> list[DetectedIssue]:
    issues: list[DetectedIssue] = []
    objective = content.get("objective")
    if not isinstance(objective, dict) or not _text(objective.get("primary_goal")):
        issues.append(_missing("objective.primary_goal", "Primary objective is required"))
    audience = content.get("audience")
    if not isinstance(audience, dict) or not _text(audience.get("primary_audience")):
        issues.append(_missing("audience.primary_audience", "Primary audience is required"))

    deliverables = content.get("deliverables")
    durations = deliverables.get("duration_seconds") if isinstance(deliverables, dict) else None
    if not isinstance(durations, list) or not durations:
        issues.append(_missing("deliverables.duration_seconds", "Duration is required"))
    elif len(set(durations)) > 1:
        issues.append(
            DetectedIssue(
                RequirementIssueType.CONFLICTING,
                "deliverables.duration_seconds",
                RequirementIssueSeverity.BLOCKING,
                "Multiple conflicting durations are declared",
            )
        )

    creative = content.get("creative_constraints")
    if not isinstance(creative, dict) or not _text(creative.get("call_to_action")):
        issues.append(_missing("creative_constraints.call_to_action", "Call to action is required"))

    compliance = content.get("legal_and_compliance")
    if isinstance(compliance, dict) and _text(compliance.get("regulated_category")):
        disclaimers = compliance.get("disclaimer_requirements")
        if not isinstance(disclaimers, list) or not disclaimers:
            issues.append(
                DetectedIssue(
                    RequirementIssueType.COMPLIANCE_RISK,
                    "legal_and_compliance.disclaimer_requirements",
                    RequirementIssueSeverity.BLOCKING,
                    "Regulated content requires at least one disclaimer",
                )
            )
    return issues


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _missing(path: str, message: str) -> DetectedIssue:
    return DetectedIssue(
        RequirementIssueType.MISSING,
        path,
        RequirementIssueSeverity.BLOCKING,
        message,
    )
