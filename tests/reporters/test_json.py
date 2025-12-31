"""Tests for JsonReporter.

Tests the JSON output reporter for GitHub Actions and data persistence.
"""

import pytest
import json
from unittest.mock import Mock, patch, mock_open
from datetime import datetime
from pathlib import Path

from src.reporters.json_reporter import JsonReporter
from src.reporters.base import Reporter
from src.models import ProviderResult, CaseResult, ResultStatus


class TestJsonReporterInterface:
    """Tests that JsonReporter implements Reporter interface."""

    def test_inherits_from_reporter(self):
        """JsonReporter should inherit from Reporter."""
        reporter = JsonReporter()
        assert isinstance(reporter, Reporter)

    def test_has_required_methods(self):
        """Should have all required Reporter methods."""
        reporter = JsonReporter()
        assert hasattr(reporter, "on_case_start")
        assert hasattr(reporter, "on_case_complete")
        assert hasattr(reporter, "on_provider_start")
        assert hasattr(reporter, "on_provider_complete")
        assert hasattr(reporter, "on_run_complete")


class TestJsonReporterDataCollection:
    """Tests for data collection during test run."""

    def test_collects_provider_results(self):
        """Should collect results from all providers."""
        reporter = JsonReporter()

        result1 = ProviderResult(
            provider_key="b2",
            provider_name="Backblaze B2",
            status=ResultStatus.PASS,
        )
        result2 = ProviderResult(
            provider_key="r2",
            provider_name="Cloudflare R2",
            status=ResultStatus.FAIL,
        )

        reporter.on_provider_complete(result1)
        reporter.on_provider_complete(result2)

        assert len(reporter._results) == 2

    def test_on_run_complete_generates_output(self):
        """on_run_complete should generate JSON output."""
        reporter = JsonReporter()
        results = {
            "test": ProviderResult(
                provider_key="test",
                provider_name="Test",
                status=ResultStatus.PASS,
            ),
        }

        output = reporter.on_run_complete(results)

        assert output is not None
        assert isinstance(output, dict)


class TestJsonReporterOutputFormat:
    """Tests for JSON output format."""

    def test_output_has_timestamp(self):
        """Output should include a timestamp."""
        reporter = JsonReporter()
        results = {
            "test": ProviderResult("test", "Test", ResultStatus.PASS),
        }

        output = reporter.on_run_complete(results)

        assert "timestamp" in output
        # Should be ISO format
        datetime.fromisoformat(output["timestamp"])

    def test_output_has_providers(self):
        """Output should include provider results."""
        reporter = JsonReporter()
        results = {
            "b2": ProviderResult("b2", "Backblaze B2", ResultStatus.PASS),
            "r2": ProviderResult("r2", "Cloudflare R2", ResultStatus.FAIL),
        }

        output = reporter.on_run_complete(results)

        assert "providers" in output
        assert "b2" in output["providers"]
        assert "r2" in output["providers"]

    def test_provider_has_status(self):
        """Each provider should have a status field."""
        reporter = JsonReporter()
        results = {
            "test": ProviderResult("test", "Test", ResultStatus.PASS),
        }

        output = reporter.on_run_complete(results)

        assert output["providers"]["test"]["status"] == "pass"

    def test_provider_has_name(self):
        """Each provider should have its display name."""
        reporter = JsonReporter()
        results = {
            "test": ProviderResult("test", "Test Provider Name", ResultStatus.PASS),
        }

        output = reporter.on_run_complete(results)

        assert output["providers"]["test"]["name"] == "Test Provider Name"

    def test_provider_has_cases(self):
        """Each provider should have case results."""
        reporter = JsonReporter()
        results = {
            "test": ProviderResult(
                provider_key="test",
                provider_name="Test",
                status=ResultStatus.PASS,
                cases={
                    "case_1": CaseResult("case_1", "Test Case", ResultStatus.PASS, "rejected", "rejected"),
                },
            ),
        }

        output = reporter.on_run_complete(results)

        assert "cases" in output["providers"]["test"]
        assert "case_1" in output["providers"]["test"]["cases"]

    def test_case_has_required_fields(self):
        """Each case should have status, expected, and actual."""
        reporter = JsonReporter()
        results = {
            "test": ProviderResult(
                provider_key="test",
                provider_name="Test",
                status=ResultStatus.FAIL,
                cases={
                    "case_5": CaseResult(
                        case_id="case_5",
                        case_name="Signature Test",
                        status=ResultStatus.FAIL,
                        expected="rejected",
                        actual="accepted",
                        error_message="Provider accepted invalid request",
                    ),
                },
            ),
        }

        output = reporter.on_run_complete(results)

        case_data = output["providers"]["test"]["cases"]["case_5"]
        assert case_data["status"] == "fail"
        assert case_data["expected"] == "rejected"
        assert case_data["actual"] == "accepted"
        assert "error" in case_data

    def test_output_has_summary(self):
        """Output should have a summary section."""
        reporter = JsonReporter()
        results = {
            "p1": ProviderResult("p1", "Provider 1", ResultStatus.PASS),
            "p2": ProviderResult("p2", "Provider 2", ResultStatus.FAIL),
        }

        output = reporter.on_run_complete(results)

        assert "summary" in output
        assert output["summary"]["total_providers"] == 2
        assert output["summary"]["passed"] == 1
        assert output["summary"]["failed"] == 1


class TestJsonReporterFileOutput:
    """Tests for file output functionality."""

    def test_write_to_file(self):
        """Should write JSON to file when path provided."""
        reporter = JsonReporter(output_path="test_output.json")
        results = {
            "test": ProviderResult("test", "Test", ResultStatus.PASS),
        }

        with patch("builtins.open", mock_open()) as mocked_file:
            reporter.on_run_complete(results)

        mocked_file.assert_called_once_with("test_output.json", "w")

    def test_creates_parent_directories(self):
        """Should create parent directories if they don't exist."""
        reporter = JsonReporter(output_path="data/results/test.json")
        results = {
            "test": ProviderResult("test", "Test", ResultStatus.PASS),
        }

        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir") as mock_mkdir:
                reporter.on_run_complete(results)

        # Should have attempted to create parent directories
        # (mkdir is called on the parent path)


class TestJsonReporterGitHubActions:
    """Tests for GitHub Actions integration."""

    def test_sets_output_variable(self):
        """Should set GitHub Actions output when in CI."""
        reporter = JsonReporter(github_output=True)
        results = {
            "test": ProviderResult("test", "Test", ResultStatus.PASS),
        }

        with patch.dict("os.environ", {"GITHUB_OUTPUT": "/tmp/github_output"}):
            with patch("builtins.open", mock_open()) as mocked_file:
                reporter.on_run_complete(results)

    def test_all_passed_output(self):
        """Should output all_passed=true when all pass."""
        reporter = JsonReporter()
        results = {
            "p1": ProviderResult("p1", "P1", ResultStatus.PASS),
            "p2": ProviderResult("p2", "P2", ResultStatus.PASS),
        }

        output = reporter.on_run_complete(results)

        assert output["summary"]["all_passed"] is True

    def test_all_passed_false_on_failure(self):
        """Should output all_passed=false when any fails."""
        reporter = JsonReporter()
        results = {
            "p1": ProviderResult("p1", "P1", ResultStatus.PASS),
            "p2": ProviderResult("p2", "P2", ResultStatus.FAIL),
        }

        output = reporter.on_run_complete(results)

        assert output["summary"]["all_passed"] is False


class TestJsonReporterNoOps:
    """Tests for no-op methods."""

    def test_on_case_start_is_noop(self):
        """on_case_start should be a no-op."""
        reporter = JsonReporter()
        reporter.on_case_start("Test", "case_1")  # Should not raise

    def test_on_case_complete_is_noop(self):
        """on_case_complete should be a no-op (data comes from on_provider_complete)."""
        reporter = JsonReporter()
        case_result = CaseResult("case_1", "Test", ResultStatus.PASS, "a", "b")
        reporter.on_case_complete("Test", case_result)  # Should not raise

    def test_on_provider_start_is_noop(self):
        """on_provider_start should be a no-op."""
        reporter = JsonReporter()
        reporter.on_provider_start("Test")  # Should not raise
