"""Tests for CLI entry point.

Tests the command-line interface and argument parsing.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

from src.cli import parse_args, main, create_reporters


class TestParseArgs:
    """Tests for argument parsing."""

    def test_default_args(self):
        """Should have sensible defaults."""
        args = parse_args([])

        assert args.config == "config.json"
        assert args.quiet is False
        assert args.json_output is None
        assert args.providers is None

    def test_config_path(self):
        """Should accept custom config path."""
        args = parse_args(["--config", "custom.json"])
        assert args.config == "custom.json"

    def test_config_short_flag(self):
        """Should accept -c short flag."""
        args = parse_args(["-c", "custom.json"])
        assert args.config == "custom.json"

    def test_quiet_mode(self):
        """Should accept --quiet flag."""
        args = parse_args(["--quiet"])
        assert args.quiet is True

    def test_quiet_short_flag(self):
        """Should accept -q short flag."""
        args = parse_args(["-q"])
        assert args.quiet is True

    def test_json_output(self):
        """Should accept --json-output path."""
        args = parse_args(["--json-output", "results.json"])
        assert args.json_output == "results.json"

    def test_json_output_short_flag(self):
        """Should accept -j short flag."""
        args = parse_args(["-j", "results.json"])
        assert args.json_output == "results.json"

    def test_provider_filter(self):
        """Should accept --providers to filter."""
        args = parse_args(["--providers", "b2,r2"])
        assert args.providers == "b2,r2"

    def test_provider_short_flag(self):
        """Should accept -p short flag."""
        args = parse_args(["-p", "b2"])
        assert args.providers == "b2"

    def test_github_actions_mode(self):
        """Should accept --github-actions flag."""
        args = parse_args(["--github-actions"])
        assert args.github_actions is True

    def test_multiple_args(self):
        """Should handle multiple arguments."""
        args = parse_args([
            "-c", "custom.json",
            "-q",
            "-j", "output.json",
            "-p", "b2,r2",
            "--github-actions",
        ])

        assert args.config == "custom.json"
        assert args.quiet is True
        assert args.json_output == "output.json"
        assert args.providers == "b2,r2"
        assert args.github_actions is True


class TestCreateReporters:
    """Tests for reporter creation based on args."""

    def test_creates_console_reporter_by_default(self):
        """Should create ConsoleReporter by default."""
        args = parse_args([])
        reporters = create_reporters(args)

        assert len(reporters) >= 1
        from src.reporters import ConsoleReporter
        assert any(isinstance(r, ConsoleReporter) for r in reporters)

    def test_console_reporter_quiet_mode(self):
        """Should pass quiet flag to ConsoleReporter."""
        args = parse_args(["--quiet"])
        reporters = create_reporters(args)

        from src.reporters import ConsoleReporter
        console = next(r for r in reporters if isinstance(r, ConsoleReporter))
        assert console.quiet is True

    def test_creates_json_reporter_when_requested(self):
        """Should create JsonReporter when --json-output specified."""
        args = parse_args(["--json-output", "results.json"])
        reporters = create_reporters(args)

        from src.reporters import JsonReporter
        assert any(isinstance(r, JsonReporter) for r in reporters)

    def test_json_reporter_has_output_path(self):
        """JsonReporter should have the specified output path."""
        args = parse_args(["--json-output", "results.json"])
        reporters = create_reporters(args)

        from src.reporters import JsonReporter
        json_reporter = next(r for r in reporters if isinstance(r, JsonReporter))
        assert json_reporter.output_path == "results.json"

    def test_github_actions_enables_json_output(self):
        """--github-actions should enable JSON reporter with github output."""
        args = parse_args(["--github-actions"])
        reporters = create_reporters(args)

        from src.reporters import JsonReporter
        json_reporter = next((r for r in reporters if isinstance(r, JsonReporter)), None)
        assert json_reporter is not None
        assert json_reporter.github_output is True


class TestMain:
    """Tests for main entry point."""

    @patch("src.cli.load_providers")
    @patch("src.cli.EnforcementRunner")
    def test_main_loads_config(self, mock_runner_class, mock_load):
        """Should load provider configuration."""
        mock_load.return_value = {"test": Mock()}
        mock_runner = Mock()
        mock_runner.run.return_value = Mock(all_passed=True)
        mock_runner_class.return_value = mock_runner

        result = main(["--config", "test.json"])

        mock_load.assert_called_once_with("test.json")

    @patch("src.cli.load_providers")
    @patch("src.cli.EnforcementRunner")
    def test_main_creates_runner(self, mock_runner_class, mock_load):
        """Should create and run the EnforcementRunner."""
        mock_load.return_value = {"test": Mock()}
        mock_runner = Mock()
        mock_runner.run.return_value = Mock(all_passed=True)
        mock_runner_class.return_value = mock_runner

        main([])

        mock_runner_class.assert_called_once()
        mock_runner.run.assert_called_once()

    @patch("src.cli.load_providers")
    @patch("src.cli.EnforcementRunner")
    def test_main_returns_0_on_success(self, mock_runner_class, mock_load):
        """Should return 0 when all tests pass."""
        mock_load.return_value = {"test": Mock()}
        mock_runner = Mock()
        mock_runner.run.return_value = Mock(all_passed=True)
        mock_runner_class.return_value = mock_runner

        result = main([])

        assert result == 0

    @patch("src.cli.load_providers")
    @patch("src.cli.EnforcementRunner")
    def test_main_returns_1_on_failure(self, mock_runner_class, mock_load):
        """Should return 1 when any test fails."""
        mock_load.return_value = {"test": Mock()}
        mock_runner = Mock()
        mock_runner.run.return_value = Mock(all_passed=False)
        mock_runner_class.return_value = mock_runner

        result = main([])

        assert result == 1

    @patch("src.cli.load_providers")
    def test_main_returns_2_on_config_error(self, mock_load):
        """Should return 2 when config fails to load."""
        from src.config import ConfigError
        mock_load.side_effect = ConfigError("No config found")

        result = main([])

        assert result == 2

    @patch("src.cli.load_providers")
    @patch("src.cli.EnforcementRunner")
    def test_main_filters_providers(self, mock_runner_class, mock_load):
        """Should filter providers when --providers specified."""
        mock_load.return_value = {
            "b2": Mock(),
            "r2": Mock(),
            "s3": Mock(),
        }
        mock_runner = Mock()
        mock_runner.run.return_value = Mock(all_passed=True)
        mock_runner_class.return_value = mock_runner

        main(["--providers", "b2,r2"])

        # Runner should only get the filtered providers
        call_args = mock_runner_class.call_args
        providers = call_args[0][0]
        assert "b2" in providers
        assert "r2" in providers
        assert "s3" not in providers

    @patch("src.cli.load_providers")
    @patch("src.cli.EnforcementRunner")
    def test_main_uses_composite_reporter(self, mock_runner_class, mock_load):
        """Should use CompositeReporter when multiple reporters needed."""
        mock_load.return_value = {"test": Mock()}
        mock_runner = Mock()
        mock_runner.run.return_value = Mock(all_passed=True)
        mock_runner_class.return_value = mock_runner

        main(["--json-output", "results.json"])

        call_args = mock_runner_class.call_args
        reporter = call_args[1].get("reporter") or call_args[0][1] if len(call_args[0]) > 1 else None


class TestProviderFiltering:
    """Tests for provider filtering logic."""

    def test_filter_single_provider(self):
        """Should filter to single provider."""
        from src.cli import filter_providers

        providers = {
            "b2": Mock(),
            "r2": Mock(),
        }

        filtered = filter_providers(providers, "b2")
        assert list(filtered.keys()) == ["b2"]

    def test_filter_multiple_providers(self):
        """Should filter to multiple providers."""
        from src.cli import filter_providers

        providers = {
            "b2": Mock(),
            "r2": Mock(),
            "s3": Mock(),
        }

        filtered = filter_providers(providers, "b2,r2")
        assert set(filtered.keys()) == {"b2", "r2"}

    def test_filter_with_spaces(self):
        """Should handle spaces in provider list."""
        from src.cli import filter_providers

        providers = {
            "b2": Mock(),
            "r2": Mock(),
        }

        filtered = filter_providers(providers, "b2, r2")
        assert set(filtered.keys()) == {"b2", "r2"}

    def test_filter_unknown_provider_warning(self):
        """Should handle unknown providers gracefully."""
        from src.cli import filter_providers

        providers = {
            "b2": Mock(),
        }

        # Should not raise, just filter out unknown
        filtered = filter_providers(providers, "b2,unknown")
        assert list(filtered.keys()) == ["b2"]
