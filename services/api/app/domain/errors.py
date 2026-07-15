class DomainError(ValueError):
    code = "domain_error"


class VersionConflict(DomainError):
    code = "version_conflict"


class InvalidProjectTransition(DomainError):
    code = "invalid_project_transition"


class InvalidProjectMutation(DomainError):
    code = "invalid_project_mutation"
