class ServiceError(Exception):
    """Base for all domain errors. Routers map these to HTTP codes."""


class NotFound(ServiceError):
    pass


class Conflict(ServiceError):
    pass


class Unauthorized(ServiceError):
    pass


class Forbidden(ServiceError):
    pass


class ValidationFailed(ServiceError):
    pass
