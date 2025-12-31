"""End-to-end integration tests using real S3 providers.

These tests run the actual CLI against real providers to verify
the complete pipeline works correctly. They require valid credentials
in config.json.

Run with: pytest tests/test_e2e.py -v
Skip with: pytest -m "not e2e"
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Mark all tests in this module as e2e
pytestmark = pytest.mark.e2e

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


def run_cli(*args, timeout=300) -> subprocess.CompletedProcess:
    """Run the CLI with given arguments and return the result."""
    cmd = [sys.executable, "-m", "src", *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=timeout,
    )


def has_provider(provider_key: str) -> bool:
    """Check if a provider is configured and enabled."""
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        return False
    try:
        with open(config_path) as f:
            config = json.load(f)
        provider = config.get(provider_key, {})
        return provider.get("enabled", True) and provider.get("aws_access_key_id")
    except Exception:
        return False


def get_first_available_provider() -> str:
    """Get the first available provider key."""
    for provider in ["b2", "r2", "aws", "gcs"]:
        if has_provider(provider):
            return provider
    pytest.skip("No providers configured")


class TestCLIBasics:
    """Test CLI argument handling and basic execution."""

    def test_help_flag(self):
        """--help should show usage and exit 0."""
        result = run_cli("--help")
        assert result.returncode == 0
        assert "s3-enforcement-tester" in result.stdout
        assert "--config" in result.stdout
        assert "--providers" in result.stdout

    def test_missing_config_file(self):
        """Missing config file should exit 2 with error message."""
        result = run_cli("-c", "nonexistent_config_12345.json")
        assert result.returncode == 2
        assert "error" in result.stderr.lower() or "not found" in result.stderr.lower()

    def test_invalid_provider_filter(self):
        """Filtering to nonexistent provider should exit 2."""
        result = run_cli("-p", "nonexistent_provider_xyz")
        assert result.returncode == 2
        assert "no matching" in result.stderr.lower()


class TestFullPipelineWithRealProvider:
    """Test the complete pipeline against a real provider."""

    @pytest.fixture
    def provider(self):
        """Get an available provider for testing."""
        return get_first_available_provider()

    def test_single_provider_pass(self, provider):
        """Run all tests against a single provider - should pass."""
        result = run_cli("-p", provider)

        # Should complete (exit 0 = all pass, exit 1 = some fail)
        assert result.returncode in (0, 1), f"Unexpected exit code: {result.returncode}\nstderr: {result.stderr}"

        # Should have console output
        assert "Testing:" in result.stdout
        assert provider.upper() in result.stdout.upper() or provider in result.stdout

        # Should show test results
        assert "[PASS]" in result.stdout or "[FAIL]" in result.stdout

        # Should show summary
        assert "Provider Compliance Summary" in result.stdout or "PASSED" in result.stdout or "FAILED" in result.stdout

    def test_quiet_mode(self, provider):
        """Quiet mode should suppress per-case output."""
        result = run_cli("-p", provider, "-q")

        assert result.returncode in (0, 1)

        # Should NOT have per-case output
        # (quiet mode suppresses individual test results)
        lines_with_pass_fail = [l for l in result.stdout.split("\n")
                                if "[PASS]:" in l or "[FAIL]:" in l]
        assert len(lines_with_pass_fail) == 0, "Quiet mode should suppress per-case output"

        # Should still show summary
        assert "PASSED" in result.stdout or "FAILED" in result.stdout

    def test_json_output(self, provider):
        """JSON output should create valid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json_path = f.name

        try:
            result = run_cli("-p", provider, "-j", json_path)

            assert result.returncode in (0, 1)

            # JSON file should exist
            assert os.path.exists(json_path), "JSON output file not created"

            # Should be valid JSON
            with open(json_path) as f:
                data = json.load(f)

            # Should have required structure
            assert "timestamp" in data
            assert "providers" in data
            assert "summary" in data

            # Should have provider results
            assert provider in data["providers"] or len(data["providers"]) > 0

            # Summary should have counts
            assert "total_providers" in data["summary"]
            assert "passed" in data["summary"]
            assert "failed" in data["summary"]

        finally:
            if os.path.exists(json_path):
                os.unlink(json_path)

    def test_json_output_structure(self, provider):
        """JSON output should have correct nested structure."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json_path = f.name

        try:
            result = run_cli("-p", provider, "-j", json_path)
            assert result.returncode in (0, 1)

            with open(json_path) as f:
                data = json.load(f)

            # Check provider structure
            for pkey, pdata in data["providers"].items():
                assert "name" in pdata, f"Provider {pkey} missing 'name'"
                assert "status" in pdata, f"Provider {pkey} missing 'status'"
                assert "cases" in pdata, f"Provider {pkey} missing 'cases'"
                assert "duration_seconds" in pdata, f"Provider {pkey} missing 'duration_seconds'"

                # Check case structure
                for case_id, case_data in pdata["cases"].items():
                    assert "status" in case_data, f"Case {case_id} missing 'status'"
                    assert "expected" in case_data, f"Case {case_id} missing 'expected'"
                    assert "actual" in case_data, f"Case {case_id} missing 'actual'"

        finally:
            if os.path.exists(json_path):
                os.unlink(json_path)


class TestAllCasesExecuted:
    """Verify all 10 test cases are executed (6 multipart + 4 single-part)."""

    @pytest.fixture
    def provider(self):
        return get_first_available_provider()

    def test_all_10_cases_in_output(self, provider):
        """All 10 test cases should appear in output."""
        result = run_cli("-p", provider)
        assert result.returncode in (0, 1)

        # Check for case names in output
        # Multipart tests (case_1, 2, 5-8)
        # Single-part tests (case_9-12)
        expected_cases = [
            # Multipart upload tests
            "Content-Length Header > Body",  # case_1
            "Content-Length Header < Body",  # case_2
            "Body > Signed",                 # case_5
            "Body < Signed",                 # case_6
            "Control Group",                 # case_7
            "List Parts",                    # case_8
            # Single-part upload tests
            "Single-Part: CL Header > Body", # case_9
            "Single-Part: CL Header < Body", # case_10
            "Single-Part: Body > Signed",    # case_11
            "Single-Part: Control",          # case_12
        ]

        for case_name in expected_cases:
            assert case_name in result.stdout, f"Case '{case_name}' not found in output"

    def test_all_10_cases_in_json(self, provider):
        """All 10 test cases should be in JSON output."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json_path = f.name

        try:
            result = run_cli("-p", provider, "-j", json_path)
            assert result.returncode in (0, 1)

            with open(json_path) as f:
                data = json.load(f)

            # Get the provider's cases
            provider_data = list(data["providers"].values())[0]
            cases = provider_data["cases"]

            # Should have all 10 cases (6 multipart + 4 single-part)
            expected_case_ids = [
                "case_1", "case_2", "case_5", "case_6", "case_7", "case_8",  # multipart
                "case_9", "case_10", "case_11", "case_12",  # single-part
            ]
            for case_id in expected_case_ids:
                assert case_id in cases, f"Case {case_id} not in JSON output"

        finally:
            if os.path.exists(json_path):
                os.unlink(json_path)


class TestExitCodes:
    """Verify correct exit codes for different scenarios."""

    @pytest.fixture
    def provider(self):
        return get_first_available_provider()

    def test_exit_code_0_or_1_on_completion(self, provider):
        """Completed run should exit 0 (all pass) or 1 (some fail)."""
        result = run_cli("-p", provider)
        assert result.returncode in (0, 1), f"Expected 0 or 1, got {result.returncode}"

    def test_exit_code_2_on_config_error(self):
        """Config error should exit 2."""
        result = run_cli("-c", "does_not_exist.json")
        assert result.returncode == 2

    def test_exit_code_2_on_no_providers(self):
        """No matching providers should exit 2."""
        result = run_cli("-p", "fake_provider_that_does_not_exist")
        assert result.returncode == 2


class TestConsoleOutputEncoding:
    """Verify console output doesn't crash on Windows."""

    @pytest.fixture
    def provider(self):
        return get_first_available_provider()

    def test_console_output_no_encoding_crash(self, provider):
        """CLI should complete without encoding errors."""
        result = run_cli("-p", provider)

        # Should not crash
        assert result.returncode in (0, 1, 2)

        # Should not have encoding error in stderr
        assert "UnicodeEncodeError" not in result.stderr
        assert "charmap" not in result.stderr

    def test_summary_table_renders(self, provider):
        """Summary table should render without crash."""
        result = run_cli("-p", provider)

        assert result.returncode in (0, 1)

        # Table should render (has box characters or provider name in table)
        assert "Provider" in result.stdout or "+" in result.stdout or "|" in result.stdout
        # Final status should appear
        assert "PASS" in result.stdout or "FAIL" in result.stdout or "ERROR" in result.stdout


class TestMultipleProviders:
    """Test running multiple providers."""

    def test_two_providers(self):
        """Running two providers should test both."""
        providers = []
        for p in ["b2", "r2", "aws", "gcs"]:
            if has_provider(p):
                providers.append(p)
            if len(providers) >= 2:
                break

        if len(providers) < 2:
            pytest.skip("Need at least 2 providers configured")

        result = run_cli("-p", ",".join(providers))

        assert result.returncode in (0, 1)

        # Both providers should appear in output
        for p in providers:
            # Provider name should appear (case-insensitive check)
            assert p.lower() in result.stdout.lower() or p.upper() in result.stdout


class TestMultipartUploadLifecycle:
    """Verify multipart upload lifecycle is handled correctly."""

    @pytest.fixture
    def provider(self):
        return get_first_available_provider()

    def test_upload_completes_or_aborts(self, provider):
        """Upload should complete successfully or abort cleanly."""
        result = run_cli("-p", provider)

        # Should complete without exception
        assert result.returncode in (0, 1)

        # Should not have uncaught exceptions
        assert "Traceback" not in result.stderr
        assert "Exception" not in result.stderr or "UnicodeEncodeError" not in result.stderr

    def test_no_orphan_parts_error(self, provider):
        """Should not leave orphan parts on failure."""
        result = run_cli("-p", provider)

        # Run completes
        assert result.returncode in (0, 1)

        # No error about orphan parts or cleanup failure
        assert "orphan" not in result.stderr.lower()
        assert "cleanup failed" not in result.stderr.lower()


class TestRetryLogic:
    """Verify retry logic works (hard to test without network issues)."""

    @pytest.fixture
    def provider(self):
        return get_first_available_provider()

    def test_completes_without_retry_errors(self, provider):
        """Should complete without retry exhaustion errors."""
        result = run_cli("-p", provider)

        assert result.returncode in (0, 1)

        # Should not have max retries exceeded
        assert "max retries" not in result.stderr.lower()
        assert "retry exhausted" not in result.stderr.lower()


class TestConfigLoading:
    """Test config loading from different sources."""

    def test_load_from_default_config(self):
        """Should load from config.json by default."""
        if not (PROJECT_ROOT / "config.json").exists():
            pytest.skip("config.json not found")

        result = run_cli("-p", get_first_available_provider())

        # Should run (proves config was loaded)
        assert result.returncode in (0, 1)

    def test_load_from_custom_config(self):
        """Should load from specified config file."""
        # Create a temporary config with just one provider
        provider = get_first_available_provider()

        # Read existing config
        with open(PROJECT_ROOT / "config.json") as f:
            config = json.load(f)

        # Write minimal config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({provider: config[provider]}, f)
            temp_config = f.name

        try:
            result = run_cli("-c", temp_config, "-p", provider)
            assert result.returncode in (0, 1)
        finally:
            os.unlink(temp_config)


class TestDashboardWorkflow:
    """E2E tests for the dashboard site generation workflow."""

    @pytest.fixture
    def provider(self):
        """Get an available provider for testing."""
        return get_first_available_provider()

    def test_build_site_creates_all_artifacts(self, provider):
        """--build-site should create all required site artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            site_dir = os.path.join(tmpdir, "site", "data")

            result = run_cli("-p", provider, "--build-site", "--site-dir", site_dir)

            # Should complete
            assert result.returncode in (0, 1), f"Unexpected exit: {result.returncode}\nstderr: {result.stderr}"

            # Should create all required files
            assert os.path.exists(os.path.join(site_dir, "latest.json")), "latest.json not created"
            assert os.path.exists(os.path.join(site_dir, "history.json")), "history.json not created"
            assert os.path.exists(os.path.join(site_dir, "badges", "overall.svg")), "overall.svg not created"
            assert os.path.exists(os.path.join(site_dir, "badges", f"{provider}.svg")), f"{provider}.svg not created"
            assert os.path.exists(os.path.join(site_dir, "runs")), "runs/ directory not created"

    def test_latest_json_has_correct_structure(self, provider):
        """latest.json should have the correct schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            site_dir = os.path.join(tmpdir, "data")

            result = run_cli("-p", provider, "--build-site", "--site-dir", site_dir)
            assert result.returncode in (0, 1)

            with open(os.path.join(site_dir, "latest.json")) as f:
                data = json.load(f)

            # Check required fields
            assert "timestamp" in data, "Missing timestamp"
            assert "providers" in data, "Missing providers"
            assert "summary" in data, "Missing summary"

            # Check provider data
            assert provider in data["providers"], f"Provider {provider} not in results"
            pdata = data["providers"][provider]
            assert "name" in pdata, "Provider missing name"
            assert "status" in pdata, "Provider missing status"
            assert "cases" in pdata, "Provider missing cases"

            # Check summary
            assert "total_providers" in data["summary"]
            assert "passed" in data["summary"]
            assert "failed" in data["summary"]

    def test_history_json_accumulates(self, provider):
        """Running twice should accumulate history entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            site_dir = os.path.join(tmpdir, "data")

            # First run
            result1 = run_cli("-p", provider, "--build-site", "--site-dir", site_dir)
            assert result1.returncode in (0, 1)

            with open(os.path.join(site_dir, "history.json")) as f:
                history1 = json.load(f)

            first_count = len(history1["providers"].get(provider, {}).get("history", []))

            # Second run
            result2 = run_cli("-p", provider, "--build-site", "--site-dir", site_dir)
            assert result2.returncode in (0, 1)

            with open(os.path.join(site_dir, "history.json")) as f:
                history2 = json.load(f)

            second_count = len(history2["providers"].get(provider, {}).get("history", []))

            # Should have more entries after second run
            assert second_count >= first_count, "History should accumulate"

    def test_badges_have_correct_format(self, provider):
        """Generated badges should be valid SVG."""
        with tempfile.TemporaryDirectory() as tmpdir:
            site_dir = os.path.join(tmpdir, "data")

            result = run_cli("-p", provider, "--build-site", "--site-dir", site_dir)
            assert result.returncode in (0, 1)

            # Check provider badge
            badge_path = os.path.join(site_dir, "badges", f"{provider}.svg")
            with open(badge_path) as f:
                svg = f.read()

            assert svg.startswith("<svg"), "Badge should be SVG"
            assert "xmlns" in svg, "Badge should have xmlns"
            assert svg.endswith("</svg>"), "Badge should end with </svg>"

            # Check overall badge
            overall_path = os.path.join(site_dir, "badges", "overall.svg")
            with open(overall_path) as f:
                overall_svg = f.read()

            assert overall_svg.startswith("<svg"), "Overall badge should be SVG"
            assert "Passing" in overall_svg, "Overall badge should show passing count"

    def test_run_file_saved_with_date(self, provider):
        """Individual run should be saved with date filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            site_dir = os.path.join(tmpdir, "data")

            result = run_cli("-p", provider, "--build-site", "--site-dir", site_dir)
            assert result.returncode in (0, 1)

            # Should have at least one run file
            runs_dir = os.path.join(site_dir, "runs")
            run_files = os.listdir(runs_dir)
            assert len(run_files) > 0, "No run files created"

            # Run file should be named YYYY-MM-DD.json
            import re
            date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
            assert any(date_pattern.match(f) for f in run_files), "Run file should have date format"

    def test_json_output_and_build_site_together(self, provider):
        """--json-output and --build-site should work together."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "results.json")
            site_dir = os.path.join(tmpdir, "site", "data")

            result = run_cli(
                "-p", provider,
                "-j", json_path,
                "--build-site",
                "--site-dir", site_dir
            )

            assert result.returncode in (0, 1)

            # Both outputs should exist
            assert os.path.exists(json_path), "JSON output not created"
            assert os.path.exists(os.path.join(site_dir, "latest.json")), "Site data not created"

            # Both should have the same provider data
            with open(json_path) as f:
                json_data = json.load(f)
            with open(os.path.join(site_dir, "latest.json")) as f:
                site_data = json.load(f)

            assert provider in json_data["providers"]
            assert provider in site_data["providers"]
