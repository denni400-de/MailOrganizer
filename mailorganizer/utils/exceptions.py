"""Custom exceptions used across MailOrganizer."""


class MailOrganizerError(Exception):
    """Base exception for all application-specific errors."""


class MailConnectionError(MailOrganizerError):
    """Raised when connecting to an IMAP/SMTP server fails."""


class MailFetchError(MailOrganizerError):
    """Raised when fetching mails from the server fails."""


class MailSendError(MailOrganizerError):
    """Raised when sending a mail fails."""


class OllamaConnectionError(MailOrganizerError):
    """Raised when connecting to the Ollama server fails."""


class OllamaResponseError(MailOrganizerError):
    """Raised when Ollama returns an unexpected or unparsable response."""


class AnalysisError(MailOrganizerError):
    """Raised when analyzing a mail fails."""


class StorageError(MailOrganizerError):
    """Raised when a database operation fails."""


class ValidationError(MailOrganizerError):
    """Raised when input validation fails."""


class CredentialError(MailOrganizerError):
    """Raised when encrypting/decrypting credentials fails."""
