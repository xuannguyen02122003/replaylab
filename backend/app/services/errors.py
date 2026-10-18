"""Domain errors raised by services. The API layer maps them to HTTP status codes."""


class ServiceError(Exception):
    code = "service_error"
    status_code = 400

    def __init__(self, message: str, details: object | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(ServiceError):
    code = "not_found"
    status_code = 404


class ConflictError(ServiceError):
    code = "conflict"
    status_code = 409


class InvalidTraceError(ServiceError):
    code = "invalid_trace"
    status_code = 422


class FeatureDisabledError(ServiceError):
    code = "feature_disabled"
    status_code = 403
