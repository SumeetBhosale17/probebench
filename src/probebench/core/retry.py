import logging
import time
from collections.abc import Callable

import httpx
from ollama import ResponseError

logger = logging.getLogger(__name__)

# 404 is deliberately retryable. On a memory-thrashing host, Ollama can briefly
# fail to resolve a model it is mid-unload. A genuinely absent model is caught
# by OllamaModelRegistry.ensure_available() before the run starts, so a 404 here
# is far more likely to be transient than real.

RETRYABLE_STATUS = {404, 500, 502, 503, 504}


def with_retries[T](
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    backoff_sec: float = 2.0,
    description: str = "ollama call",
) -> T:
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except ResponseError as exc:
            if exc.status_code not in RETRYABLE_STATUS:
                raise
            last_error = exc
        except (
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ) as exc:
            last_error = exc

        if attempt < attempts:
            delay = backoff_sec * (2 ** (attempt - 1))

            logger.warning(
                "%s failed (attempt %d/%d): %s - retrying in %.1fs",
                description,
                attempt,
                attempts,
                last_error,
                delay,
            )

            time.sleep(delay)

    assert last_error is not None
    raise last_error
