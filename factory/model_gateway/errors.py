"""Errors shared by every model provider, so steps never depend on which one runs."""


class ModelUnavailable(RuntimeError):
    """The model endpoint is not configured, not reachable, or its SDK is missing.

    Steps treat this as "park or fall back", never as a case failure.
    """
