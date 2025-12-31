"""Integration tests for real HTTP behavior and CLI execution.

These tests verify that the actual HTTP client behavior matches our expectations,
especially around content-length validation which is critical for the enforcement
tests to work correctly.

These tests do NOT require real S3 credentials - they use a local mock server.
"""

import pytest
import httpx
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import StringIO
from unittest.mock import patch

from h11 import LocalProtocolError as H11LocalProtocolError


class MockS3Handler(BaseHTTPRequestHandler):
    """Mock HTTP handler that simulates S3 upload behavior."""

    def log_message(self, format, *args):
        """Suppress logging."""
        pass

    def do_PUT(self):
        """Handle PUT requests - just accept and return 200."""
        content_length = int(self.headers.get("Content-Length", 0))
        # Read the body
        body = self.rfile.read(content_length)
        # Send success response
        self.send_response(200)
        self.send_header("ETag", '"mock-etag-12345"')
        self.end_headers()


@pytest.fixture(scope="module")
def mock_server():
    """Start a mock HTTP server for integration tests."""
    server = HTTPServer(("127.0.0.1", 0), MockS3Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


class TestRealHttpContentLengthValidation:
    """Test that httpx actually raises the expected exceptions.

    These tests verify that our understanding of httpx/h11 behavior is correct.
    If these tests fail, it means httpx behavior changed and we need to update
    our exception handling.
    """

    def test_h11_raises_too_little_data_error(self, mock_server):
        """Verify h11 raises LocalProtocolError when body < Content-Length header.

        This is the actual exception that Cases 1 and 3 rely on.
        """
        with httpx.Client() as client:
            # Claim 100 bytes but only send 50
            def body_gen():
                yield b"x" * 50

            with pytest.raises(H11LocalProtocolError) as exc_info:
                client.put(
                    f"{mock_server}/test",
                    content=body_gen(),
                    headers={"Content-Length": "100"},
                )

            assert "Too little data" in str(exc_info.value)

    def test_h11_raises_too_much_data_error(self, mock_server):
        """Verify h11 raises LocalProtocolError when body > Content-Length header.

        This is the actual exception that Cases 2 and 4 rely on.
        """
        with httpx.Client() as client:
            # Claim 50 bytes but send 100
            def body_gen():
                yield b"x" * 100

            with pytest.raises(H11LocalProtocolError) as exc_info:
                client.put(
                    f"{mock_server}/test",
                    content=body_gen(),
                    headers={"Content-Length": "50"},
                )

            assert "Too much data" in str(exc_info.value)

    def test_valid_request_succeeds(self, mock_server):
        """Verify valid request with matching content-length succeeds.

        This is what Case 7 (control group) relies on.
        """
        with httpx.Client() as client:
            data = b"x" * 100

            def body_gen():
                yield data

            response = client.put(
                f"{mock_server}/test",
                content=body_gen(),
                headers={"Content-Length": str(len(data))},
            )

            assert response.status_code == 200
            assert response.headers.get("ETag") is not None


class TestConsoleOutputEncoding:
    """Test that console output works with various encodings.

    These tests verify that our Rich output doesn't use characters
    that can't be encoded on Windows consoles.
    """

    def test_console_reporter_uses_ascii_safe_characters(self):
        """Verify ConsoleReporter output can be encoded as ASCII."""
        from src.reporters.console import ConsoleReporter
        from src.models import CaseResult, ProviderResult, ResultStatus

        reporter = ConsoleReporter(quiet=False)

        # Create test data
        case_result = CaseResult(
            case_id="case_1",
            case_name="Test Case",
            status=ResultStatus.PASS,
            expected="rejected",
            actual="rejected",
        )

        provider_result = ProviderResult(
            provider_key="test",
            provider_name="Test Provider",
            status=ResultStatus.PASS,
            cases={"case_1": case_result},
            duration_seconds=1.5,
        )

        # Capture output - test with the same settings as production
        from io import StringIO
        from rich.console import Console

        output = StringIO()
        # Match production settings: legacy_windows=True for ASCII-safe output
        test_console = Console(
            file=output,
            force_terminal=False,
            no_color=True,
            legacy_windows=True,
        )
        reporter.console = test_console

        # These should not raise encoding errors
        reporter.on_case_complete("Test Provider", case_result)
        reporter.on_provider_complete(provider_result)
        reporter.on_run_complete({"test": provider_result})

        # Verify output is ASCII-encodable (cp1252 compatible)
        output_text = output.getvalue()
        try:
            output_text.encode("cp1252")
        except UnicodeEncodeError as e:
            pytest.fail(f"Console output contains characters not encodable in cp1252: {e}")

    def test_console_reporter_fail_status_ascii_safe(self):
        """Verify FAIL status output is cp1252-safe."""
        from src.reporters.console import ConsoleReporter
        from src.models import CaseResult, ProviderResult, ResultStatus

        reporter = ConsoleReporter(quiet=False)

        case_result = CaseResult(
            case_id="case_1",
            case_name="Test Case",
            status=ResultStatus.FAIL,
            expected="rejected",
            actual="accepted",
            error_message="Provider incorrectly accepted",
        )

        provider_result = ProviderResult(
            provider_key="test",
            provider_name="Test Provider",
            status=ResultStatus.FAIL,
            cases={"case_1": case_result},
            duration_seconds=1.5,
        )

        from io import StringIO
        from rich.console import Console

        output = StringIO()
        test_console = Console(
            file=output,
            force_terminal=False,
            no_color=True,
            legacy_windows=True,
        )
        reporter.console = test_console

        reporter.on_case_complete("Test Provider", case_result)
        reporter.on_provider_complete(provider_result)
        reporter.on_run_complete({"test": provider_result})

        output_text = output.getvalue()
        try:
            output_text.encode("cp1252")
        except UnicodeEncodeError as e:
            pytest.fail(f"Console output contains characters not encodable in cp1252: {e}")

    def test_console_reporter_error_status_ascii_safe(self):
        """Verify ERROR status output is cp1252-safe."""
        from src.reporters.console import ConsoleReporter
        from src.models import CaseResult, ProviderResult, ResultStatus

        reporter = ConsoleReporter(quiet=False)

        case_result = CaseResult(
            case_id="case_1",
            case_name="Test Case",
            status=ResultStatus.ERROR,
            expected="rejected",
            actual="error",
            error_message="Connection timeout",
        )

        provider_result = ProviderResult(
            provider_key="test",
            provider_name="Test Provider",
            status=ResultStatus.ERROR,
            cases={"case_1": case_result},
            duration_seconds=1.5,
            error_message="Provider error",
        )

        from io import StringIO
        from rich.console import Console

        output = StringIO()
        test_console = Console(
            file=output,
            force_terminal=False,
            no_color=True,
            legacy_windows=True,
        )
        reporter.console = test_console

        reporter.on_case_complete("Test Provider", case_result)
        reporter.on_provider_complete(provider_result)
        reporter.on_run_complete({"test": provider_result})

        output_text = output.getvalue()
        try:
            output_text.encode("cp1252")
        except UnicodeEncodeError as e:
            pytest.fail(f"Console output contains characters not encodable in cp1252: {e}")


class TestCLIIntegration:
    """Test full CLI execution paths."""

    def test_cli_help_works(self):
        """Verify CLI help runs without error."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "src", "--help"],
            capture_output=True,
            text=True,
            cwd=r"p:\Drone\Apps\_Utilities\S3UploadEnforcementTest",
        )

        assert result.returncode == 0
        assert "s3-enforcement-tester" in result.stdout

    def test_cli_missing_config_returns_error_code(self):
        """Verify CLI returns exit code 2 when config is missing."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "src", "-c", "nonexistent.json"],
            capture_output=True,
            text=True,
            cwd=r"p:\Drone\Apps\_Utilities\S3UploadEnforcementTest",
        )

        assert result.returncode == 2
        assert "Configuration error" in result.stderr or "error" in result.stderr.lower()

    def test_cli_no_matching_providers_returns_error_code(self):
        """Verify CLI returns exit code 2 when no providers match filter."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "src", "-p", "nonexistent_provider"],
            capture_output=True,
            text=True,
            cwd=r"p:\Drone\Apps\_Utilities\S3UploadEnforcementTest",
        )

        assert result.returncode == 2
        assert "No matching providers" in result.stderr


class TestExceptionHierarchy:
    """Verify our understanding of exception hierarchies is correct.

    If these tests fail, the exception handling code may need updating.
    """

    def test_h11_and_httpx_local_protocol_error_are_different_types(self):
        """Verify h11.LocalProtocolError is NOT a subclass of httpx.LocalProtocolError."""
        assert not issubclass(H11LocalProtocolError, httpx.LocalProtocolError)
        assert not issubclass(httpx.LocalProtocolError, H11LocalProtocolError)

    def test_httpx_exports_local_protocol_error(self):
        """Verify httpx exports LocalProtocolError at package level."""
        assert hasattr(httpx, "LocalProtocolError")

    def test_both_exception_types_can_be_caught(self):
        """Verify we can catch both exception types in a single except clause."""
        caught = False

        try:
            raise H11LocalProtocolError("test error")
        except (httpx.LocalProtocolError, H11LocalProtocolError):
            caught = True

        assert caught, "h11.LocalProtocolError should be catchable"

        caught = False
        try:
            raise httpx.LocalProtocolError("test error")
        except (httpx.LocalProtocolError, H11LocalProtocolError):
            caught = True

        assert caught, "httpx.LocalProtocolError should be catchable"
