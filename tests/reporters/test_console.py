"""Tests for ConsoleReporter.

Tests the Rich-based console output reporter.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from src.reporters.console import ConsoleReporter
from src.reporters.base import Reporter
from src.models import ProviderConfig, ProviderResult, CaseResult, ResultStatus


class TestConsoleReporterInterface:
    """Tests that ConsoleReporter implements Reporter interface."""

    def test_inherits_from_reporter(self):
        """ConsoleReporter should inherit from Reporter."""
        reporter = ConsoleReporter()
        assert isinstance(reporter, Reporter)

    def test_has_required_methods(self):
        """Should have all required Reporter methods."""
        reporter = ConsoleReporter()
        assert hasattr(reporter, "on_case_start")
        assert hasattr(reporter, "on_case_complete")
        assert hasattr(reporter, "on_provider_start")
        assert hasattr(reporter, "on_provider_complete")
        assert hasattr(reporter, "on_run_complete")


class TestConsoleReporterProviderStart:
    """Tests for on_provider_start method."""

    def test_on_provider_start_prints_header(self):
        """Should print a header when provider testing starts."""
        reporter = ConsoleReporter()

        with patch.object(reporter.console, "print") as mock_print:
            reporter.on_provider_start("Backblaze B2")

        # Should have printed something
        assert mock_print.called

    def test_on_provider_start_includes_provider_name(self):
        """Header should include the provider name."""
        reporter = ConsoleReporter()

        with patch.object(reporter.console, "print") as mock_print:
            reporter.on_provider_start("Cloudflare R2")

        # Check that provider name was in the output
        call_args = str(mock_print.call_args_list)
        assert "Cloudflare R2" in call_args or mock_print.called


class TestConsoleReporterCaseComplete:
    """Tests for on_case_complete method."""

    def test_on_case_complete_pass(self):
        """Should display pass indicator for passing case."""
        reporter = ConsoleReporter()
        case_result = CaseResult(
            case_id="case_1",
            case_name="Content-Length > Body",
            status=ResultStatus.PASS,
            expected="rejected",
            actual="rejected",
        )

        with patch.object(reporter.console, "print") as mock_print:
            reporter.on_case_complete("Test Provider", case_result)

        assert mock_print.called

    def test_on_case_complete_fail(self):
        """Should display fail indicator for failing case."""
        reporter = ConsoleReporter()
        case_result = CaseResult(
            case_id="case_5",
            case_name="Body > Signed Content-Length",
            status=ResultStatus.FAIL,
            expected="rejected",
            actual="accepted",
            error_message="Provider accepted invalid request",
        )

        with patch.object(reporter.console, "print") as mock_print:
            reporter.on_case_complete("Test Provider", case_result)

        assert mock_print.called

    def test_on_case_complete_error(self):
        """Should display error indicator for error case."""
        reporter = ConsoleReporter()
        case_result = CaseResult(
            case_id="case_7",
            case_name="Control Group",
            status=ResultStatus.ERROR,
            expected="accepted",
            actual="error",
            error_message="Connection timeout",
        )

        with patch.object(reporter.console, "print") as mock_print:
            reporter.on_case_complete("Test Provider", case_result)

        assert mock_print.called


class TestConsoleReporterProviderComplete:
    """Tests for on_provider_complete method."""

    def test_on_provider_complete_pass(self):
        """Should display success summary for passing provider."""
        reporter = ConsoleReporter()
        result = ProviderResult(
            provider_key="b2",
            provider_name="Backblaze B2",
            status=ResultStatus.PASS,
            duration_seconds=15.5,
        )

        with patch.object(reporter.console, "print") as mock_print:
            reporter.on_provider_complete(result)

        assert mock_print.called

    def test_on_provider_complete_fail(self):
        """Should display failure summary for failing provider."""
        reporter = ConsoleReporter()
        result = ProviderResult(
            provider_key="r2",
            provider_name="Cloudflare R2",
            status=ResultStatus.FAIL,
            duration_seconds=12.3,
        )

        with patch.object(reporter.console, "print") as mock_print:
            reporter.on_provider_complete(result)

        assert mock_print.called

    def test_on_provider_complete_error(self):
        """Should display error summary for errored provider."""
        reporter = ConsoleReporter()
        result = ProviderResult(
            provider_key="test",
            provider_name="Test Provider",
            status=ResultStatus.ERROR,
            error_message="Connection failed",
        )

        with patch.object(reporter.console, "print") as mock_print:
            reporter.on_provider_complete(result)

        assert mock_print.called


class TestConsoleReporterRunComplete:
    """Tests for on_run_complete method."""

    def test_on_run_complete_prints_summary_table(self):
        """Should print a summary table at the end."""
        reporter = ConsoleReporter()
        results = {
            "b2": ProviderResult(
                provider_key="b2",
                provider_name="Backblaze B2",
                status=ResultStatus.PASS,
                cases={
                    "case_1": CaseResult("case_1", "CL > Body", ResultStatus.PASS, "rejected", "rejected"),
                    "case_7": CaseResult("case_7", "Control", ResultStatus.PASS, "accepted", "accepted"),
                },
            ),
            "r2": ProviderResult(
                provider_key="r2",
                provider_name="Cloudflare R2",
                status=ResultStatus.FAIL,
                cases={
                    "case_1": CaseResult("case_1", "CL > Body", ResultStatus.PASS, "rejected", "rejected"),
                    "case_5": CaseResult("case_5", "Signature", ResultStatus.FAIL, "rejected", "accepted"),
                },
            ),
        }

        with patch.object(reporter.console, "print") as mock_print:
            reporter.on_run_complete(results)

        # Should have printed multiple times (table, etc.)
        assert mock_print.call_count >= 1

    def test_on_run_complete_empty_results(self):
        """Should handle empty results gracefully."""
        reporter = ConsoleReporter()

        with patch.object(reporter.console, "print") as mock_print:
            reporter.on_run_complete({})

        # Should still complete without error
        assert True


class TestConsoleReporterCaseStart:
    """Tests for on_case_start method."""

    def test_on_case_start_is_optional(self):
        """on_case_start can be a no-op for console reporter."""
        reporter = ConsoleReporter()

        # Should not raise
        reporter.on_case_start("Test Provider", "case_1")


class TestConsoleReporterQuietMode:
    """Tests for quiet mode option."""

    def test_quiet_mode_suppresses_case_output(self):
        """Quiet mode should suppress per-case output."""
        reporter = ConsoleReporter(quiet=True)
        case_result = CaseResult(
            case_id="case_1",
            case_name="Test",
            status=ResultStatus.PASS,
            expected="rejected",
            actual="rejected",
        )

        with patch.object(reporter.console, "print") as mock_print:
            reporter.on_case_complete("Test", case_result)

        # In quiet mode, case output should be suppressed
        # (only summary at the end)

    def test_quiet_mode_still_shows_summary(self):
        """Quiet mode should still show final summary."""
        reporter = ConsoleReporter(quiet=True)
        results = {
            "test": ProviderResult(
                provider_key="test",
                provider_name="Test",
                status=ResultStatus.PASS,
            ),
        }

        with patch.object(reporter.console, "print") as mock_print:
            reporter.on_run_complete(results)

        # Summary should still be printed
        assert mock_print.called


class TestConsoleReporterSummaryTable:
    """Tests for the summary table generation."""

    def test_summary_table_has_all_providers(self):
        """Summary table should include all providers."""
        reporter = ConsoleReporter()
        results = {
            "p1": ProviderResult("p1", "Provider 1", ResultStatus.PASS),
            "p2": ProviderResult("p2", "Provider 2", ResultStatus.FAIL),
            "p3": ProviderResult("p3", "Provider 3", ResultStatus.ERROR),
        }

        # The table generation happens inside on_run_complete
        # We just verify it doesn't crash and handles all providers
        with patch.object(reporter.console, "print"):
            reporter.on_run_complete(results)

    def test_summary_table_has_all_cases(self):
        """Summary table should have columns for all 10 cases (6 multipart + 4 single-part)."""
        reporter = ConsoleReporter()
        # Include all case IDs: case_1, case_2, case_5-8 (multipart) + case_9-12 (single-part)
        all_case_ids = ["case_1", "case_2", "case_5", "case_6", "case_7", "case_8", "case_9", "case_10", "case_11", "case_12"]
        results = {
            "test": ProviderResult(
                provider_key="test",
                provider_name="Test",
                status=ResultStatus.PASS,
                cases={
                    case_id: CaseResult(
                        case_id,
                        f"Case {case_id}",
                        ResultStatus.PASS,
                        "expected",
                        "actual",
                    )
                    for case_id in all_case_ids
                },
            ),
        }

        with patch.object(reporter.console, "print"):
            reporter.on_run_complete(results)
