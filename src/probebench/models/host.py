"""Resolution of the Ollama endpoint.

Every Ollama client in ProbeBench takes its default from here so that
OLLAMA_HOST works the same way it does for the `ollama` CLI itself.
"""

import os

DEFAULT_HOST = "http://localhost:11434"


def default_ollama_host() -> str:
    """The Ollama endpoint to talk to.

    OLLAMA_HOST is commonly written without a scheme ("127.0.0.1:11434"),
    which httpx rejects, so normalize it here.
    """

    host = os.environ.get("OLLAMA_HOST", "").strip()

    if not host:
        return DEFAULT_HOST

    if "://" not in host:
        host = f"http://{host}"

    return host.rstrip("/")
