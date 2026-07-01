class MediaFlowAIError(Exception):
    """Base exception class for all errors in MediaFlow AI."""

    pass


class ConfigError(MediaFlowAIError):
    """Raised when there is an issue with application configuration."""

    pass


class DatabaseError(MediaFlowAIError):
    """Raised when database operations fail."""

    pass


class DependencyError(MediaFlowAIError):
    """Raised when dependency resolution fails."""

    pass


class JobError(MediaFlowAIError):
    """Raised when background tasks or jobs fail."""

    pass


class PluginError(MediaFlowAIError):
    """Raised when a plugin fails to load or execute."""

    pass


class ServiceError(MediaFlowAIError):
    """Base class for external service failures (e.g. AI Providers, translation)."""

    pass


class NetworkError(ServiceError):
    """Raised when a network request fails."""

    pass


class DecryptionError(MediaFlowAIError):
    """Raised when secure credentials decryption fails."""

    pass
