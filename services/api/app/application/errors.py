class ApplicationError(Exception):
    code = "application_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or type(self).code


class ResourceNotFound(ApplicationError):
    code = "resource_not_found"


class ResourceConflict(ApplicationError):
    code = "resource_conflict"


class PermissionDenied(ApplicationError):
    code = "permission_denied"


class InvalidRequest(ApplicationError):
    code = "invalid_request"


class TemporaryIdentityDisabled(ApplicationError):
    code = "temporary_identity_disabled"


class StorageUnavailable(ApplicationError):
    code = "storage_unavailable"
