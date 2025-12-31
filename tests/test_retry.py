"""Tests for retry module."""

import time
from unittest.mock import MagicMock, call

import httpx
import pytest

from src.retry import (
    is_retryable_error,
    retry_with_backoff,
    RetryExhausted,
)


class TestIsRetryableError:
    """Tests for error classification."""

    def test_connection_timeout_is_retryable(self):
        """Connection timeout should trigger retry."""
        error = httpx.ConnectTimeout("Connection timed out")
        assert is_retryable_error(error) is True

    def test_connect_error_is_retryable(self):
        """Connection error should trigger retry."""
        error = httpx.ConnectError("Connection refused")
        assert is_retryable_error(error) is True

    def test_read_timeout_is_retryable(self):
        """Read timeout should trigger retry."""
        error = httpx.ReadTimeout("Read timed out")
        assert is_retryable_error(error) is True

    def test_http_500_is_retryable(self):
        """HTTP 500 Internal Server Error should trigger retry."""
        response = MagicMock()
        response.status_code = 500
        error = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=response
        )
        assert is_retryable_error(error) is True

    def test_http_502_is_retryable(self):
        """HTTP 502 Bad Gateway should trigger retry."""
        response = MagicMock()
        response.status_code = 502
        error = httpx.HTTPStatusError(
            "Bad gateway", request=MagicMock(), response=response
        )
        assert is_retryable_error(error) is True

    def test_http_503_is_retryable(self):
        """HTTP 503 Service Unavailable should trigger retry."""
        response = MagicMock()
        response.status_code = 503
        error = httpx.HTTPStatusError(
            "Service unavailable", request=MagicMock(), response=response
        )
        assert is_retryable_error(error) is True

    def test_http_504_is_retryable(self):
        """HTTP 504 Gateway Timeout should trigger retry."""
        response = MagicMock()
        response.status_code = 504
        error = httpx.HTTPStatusError(
            "Gateway timeout", request=MagicMock(), response=response
        )
        assert is_retryable_error(error) is True

    def test_http_429_is_retryable(self):
        """HTTP 429 Too Many Requests should trigger retry."""
        response = MagicMock()
        response.status_code = 429
        error = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=response
        )
        assert is_retryable_error(error) is True

    def test_http_400_is_not_retryable(self):
        """HTTP 400 Bad Request should NOT trigger retry."""
        response = MagicMock()
        response.status_code = 400
        error = httpx.HTTPStatusError(
            "Bad request", request=MagicMock(), response=response
        )
        assert is_retryable_error(error) is False

    def test_http_401_is_not_retryable(self):
        """HTTP 401 Unauthorized should NOT trigger retry."""
        response = MagicMock()
        response.status_code = 401
        error = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=response
        )
        assert is_retryable_error(error) is False

    def test_http_403_is_not_retryable(self):
        """HTTP 403 Forbidden (signature mismatch) should NOT trigger retry."""
        response = MagicMock()
        response.status_code = 403
        error = httpx.HTTPStatusError(
            "SignatureDoesNotMatch", request=MagicMock(), response=response
        )
        assert is_retryable_error(error) is False

    def test_http_404_is_not_retryable(self):
        """HTTP 404 Not Found should NOT trigger retry."""
        response = MagicMock()
        response.status_code = 404
        error = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=response
        )
        assert is_retryable_error(error) is False

    def test_generic_exception_is_not_retryable(self):
        """Generic exceptions should NOT trigger retry by default."""
        error = ValueError("Some error")
        assert is_retryable_error(error) is False


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    def test_success_on_first_attempt(self):
        """Succeed immediately without retrying."""
        mock_func = MagicMock(return_value="success")

        result = retry_with_backoff(mock_func, max_attempts=3, delays=[1, 2, 4])

        assert result == "success"
        assert mock_func.call_count == 1

    def test_success_after_one_retry(self):
        """Succeed after one retry."""
        mock_func = MagicMock(
            side_effect=[httpx.ConnectError("fail"), "success"]
        )

        result = retry_with_backoff(
            mock_func, max_attempts=3, delays=[0.01, 0.02, 0.04]
        )

        assert result == "success"
        assert mock_func.call_count == 2

    def test_success_after_two_retries(self):
        """Succeed after two retries."""
        mock_func = MagicMock(
            side_effect=[
                httpx.ConnectError("fail1"),
                httpx.ConnectTimeout("fail2"),
                "success",
            ]
        )

        result = retry_with_backoff(
            mock_func, max_attempts=3, delays=[0.01, 0.02, 0.04]
        )

        assert result == "success"
        assert mock_func.call_count == 3

    def test_failure_after_max_retries_exceeded(self):
        """Raise RetryExhausted after all attempts fail."""
        mock_func = MagicMock(
            side_effect=httpx.ConnectError("Always fails")
        )

        with pytest.raises(RetryExhausted) as exc_info:
            retry_with_backoff(mock_func, max_attempts=3, delays=[0.01, 0.02, 0.04])

        assert mock_func.call_count == 3
        assert "3 attempts" in str(exc_info.value)

    def test_correct_delays_between_retries(self):
        """Verify delays are applied between retries."""
        mock_func = MagicMock(
            side_effect=[
                httpx.ConnectError("fail1"),
                httpx.ConnectError("fail2"),
                "success",
            ]
        )
        delays = [0.1, 0.2, 0.3]

        start = time.time()
        retry_with_backoff(mock_func, max_attempts=3, delays=delays)
        elapsed = time.time() - start

        # Should have waited at least 0.1 + 0.2 = 0.3 seconds
        assert elapsed >= 0.25  # Allow some tolerance

    def test_non_retryable_error_raises_immediately(self):
        """Non-retryable errors should raise without retry."""
        response = MagicMock()
        response.status_code = 403
        http_error = httpx.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=response
        )
        mock_func = MagicMock(side_effect=http_error)

        with pytest.raises(httpx.HTTPStatusError):
            retry_with_backoff(mock_func, max_attempts=3, delays=[0.01, 0.02, 0.04])

        # Should only be called once - no retries
        assert mock_func.call_count == 1

    def test_passes_args_and_kwargs_to_function(self):
        """Arguments and keyword arguments are passed through."""
        mock_func = MagicMock(return_value="success")

        retry_with_backoff(
            mock_func,
            max_attempts=3,
            delays=[0.01],
            args=("arg1", "arg2"),
            kwargs={"key1": "value1"},
        )

        mock_func.assert_called_with("arg1", "arg2", key1="value1")

    def test_last_error_preserved_in_retry_exhausted(self):
        """RetryExhausted should contain the last error."""
        last_error = httpx.ConnectTimeout("Final timeout")
        mock_func = MagicMock(
            side_effect=[
                httpx.ConnectError("First"),
                httpx.ConnectError("Second"),
                last_error,
            ]
        )

        with pytest.raises(RetryExhausted) as exc_info:
            retry_with_backoff(mock_func, max_attempts=3, delays=[0.01, 0.02, 0.04])

        assert exc_info.value.last_error is last_error
