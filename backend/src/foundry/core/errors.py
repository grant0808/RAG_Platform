class FoundryError(Exception):
    code = "foundry_error"
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(FoundryError):
    code = "not_found"
    status_code = 404


class ProviderError(FoundryError):
    code = "provider_error"
    status_code = 502


class ValidationError(FoundryError):
    code = "validation_error"
    status_code = 422


class ConfigurationError(FoundryError):
    code = "configuration_error"
    status_code = 409
