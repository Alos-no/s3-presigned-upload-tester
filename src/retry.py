"""Retry logic with exponential backoff for transient failures.

This module provides retry functionality for HTTP operations, with
intelligent error classification to distinguish between transient
failures (worth retrying) and permanent failures (retry won't help).

Transient (Retryable):
- Connection timeouts
- Connection errors
- Server errors (5xx)
- Rate limiting (429)

Permanent (Not Retryable):
- Client errors (4xx except 429)
- Signature mismatches (403)
- Authentication failures (401)
"""

import time
from typing import Any, Callable, Optional, Sequence

import httpx

# HTTP status codes that indicate transient server issues
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class RetryExhausted(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error is transient and worth retrying.

    Args:
        error: The exception that was raised.

    Returns:
        True if the error is transient and should trigger a retry,
        False if the error is permanent and retrying won't help.
    """
    # Network-level errors are transient
    if isinstance(error, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout)):
        return True

    # HTTP status errors need case-by-case handling
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        return status_code in RETRYABLE_STATUS_CODES

    # All other errors are not retryable by default
    return False


def retry_with_backoff(
    func: Callable[..., Any],
    max_attempts: int = 3,
    delays: Sequence[float] = (5.0, 15.0, 30.0),
    args: tuple = (),
    kwargs: Optional[dict] = None,
) -> Any:
    """Execute a function with retry logic and exponential backoff.

    Args:
        func: The function to execute.
        max_attempts: Maximum number of attempts (including first try).
        delays: Sequence of delay times (seconds) between retries.
                delays[0] is used after first failure, etc.
        args: Positional arguments to pass to func.
        kwargs: Keyword arguments to pass to func.

    Returns:
        The return value of func if successful.

    Raises:
        RetryExhausted: If all attempts fail with retryable errors.
        Exception: If a non-retryable error occurs, it's raised immediately.

    Example:
        >>> result = retry_with_backoff(
        ...     upload_part,
        ...     max_attempts=3,
        ...     delays=[5, 15, 30],
        ...     args=(url, data),
        ...     kwargs={"headers": headers},
        ... )
    """
    if kwargs is None:
        kwargs = {}

    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e

            # Check if this error is worth retrying
            if not is_retryable_error(e):
                # Permanent error - raise immediately
                raise

            # If we've exhausted all attempts, give up
            if attempt >= max_attempts:
                raise RetryExhausted(
                    f"Operation failed after {max_attempts} attempts",
                    attempts=max_attempts,
                    last_error=last_error,
                ) from last_error

            # Wait before retrying
            delay_index = min(attempt - 1, len(delays) - 1)
            delay = delays[delay_index]
            time.sleep(delay)

    # This should never be reached, but just in case
    raise RetryExhausted(
        f"Operation failed after {max_attempts} attempts",
        attempts=max_attempts,
        last_error=last_error,
    )
