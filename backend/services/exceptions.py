"""Business-layer errors translated to HTTP responses by the presentation layer."""


class ConflictError(Exception):
    pass


class NotFoundError(Exception):
    pass


class ValidationError(Exception):
    pass


class ConfigurationError(Exception):
    pass
