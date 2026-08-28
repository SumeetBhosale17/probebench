CURRENT_SCHEMA_VERSION = "1.0"


class SchemaVersionError(ValueError):
    """Raised when a result uses an unsupported schema version."""


SUPPORTED_SCHEMA_VERSIONS = {
    "1.0",
}
