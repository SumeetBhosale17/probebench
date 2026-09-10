CURRENT_SCHEMA_VERSION = "1.6"


class SchemaVersionError(ValueError):
    """Raised when a result uses an unsupported schema version."""


SUPPORTED_SCHEMA_VERSIONS = {
    "1.0",
    "1.1",
    "1.2",
    "1.3",
    "1.4",
    "1.5",
    "1.6",
}
