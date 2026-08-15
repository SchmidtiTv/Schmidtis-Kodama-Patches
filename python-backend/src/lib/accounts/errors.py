"""Safe application errors for account-scoped music operations."""


class AccountError(Exception):
    """Base error whose message is safe for an HTTP response."""

    status_code = 500
    message = "Account operation failed."

    def __init__(self, message: str | None = None) -> None:
        self.safe_message = message or self.message
        super().__init__(self.safe_message)


class AccountValidationError(AccountError):
    status_code = 400
    message = "Invalid account operation."


class AuthenticationRequiredError(AccountError):
    status_code = 401
    message = "Authentication required."


class LocalOperationNotSupportedError(AccountError):
    status_code = 403
    message = "This operation is unavailable for local profiles."


class AccountConflictError(AccountError):
    status_code = 409
    message = "Account operation conflicts with existing state."


class AccountProviderUnavailableError(AccountError):
    status_code = 502
    message = "Music provider is unavailable."


class AccountInternalError(AccountError):
    status_code = 500
    message = "Account operation failed."
