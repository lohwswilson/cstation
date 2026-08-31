class ProviderError(Exception):
    pass


class ProviderAuthError(ProviderError):
    pass


class ProviderNotFoundError(ProviderError):
    pass


class ProviderRateLimitError(ProviderError):
    pass
