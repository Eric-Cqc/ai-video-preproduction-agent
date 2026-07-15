class DomainError(ValueError):
    code = "domain_error"


class VersionConflict(DomainError):
    code = "version_conflict"


class InvalidProjectTransition(DomainError):
    code = "invalid_project_transition"


class InvalidProjectMutation(DomainError):
    code = "invalid_project_mutation"


class InvalidBriefTransition(DomainError):
    code = "invalid_brief_transition"


class InvalidBriefMutation(DomainError):
    code = "invalid_brief_mutation"


class InvalidSourceAssetMutation(DomainError):
    code = "invalid_source_asset_mutation"


class ApprovalBlocked(DomainError):
    code = "brief_approval_blocked"
