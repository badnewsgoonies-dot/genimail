"""Project-wide error types."""


class ProjectError(Exception):
    """Base for all Genimail errors."""


class ValidationError(ProjectError):
    """Invalid input data."""


class ExternalServiceError(ProjectError):
    """Third-party API or service failure."""


__all__ = ["ProjectError", "ValidationError", "ExternalServiceError"]
