class Script2GifError(Exception):
    """Base class for errors safe to present in the UI."""


class ConfigurationError(Script2GifError):
    """Raised when required local or API configuration is missing."""


class ProviderError(Script2GifError):
    """Raised when an external model provider rejects or fails a request."""


class RemoteTaskPendingError(ProviderError):
    """Raised when a resumable remote task is still running after the local timeout."""


class ProjectStoreError(Script2GifError):
    """Raised when a project cannot be loaded or persisted."""


class RenderError(Script2GifError):
    """Raised when FFmpeg rendering fails."""
