"""Command-line interface for the S3 enforcement tester.

Provides argument parsing and main entry point for running tests
from the command line.
"""

import argparse
import sys
from typing import Optional

from src.config import load_providers, ConfigError
from src.models import ProviderConfig
from src.runner import EnforcementRunner
from src.reporters import ConsoleReporter, JsonReporter, Reporter
from src.site_generator import build_site, SiteGeneratorError


class CompositeReporter(Reporter):
    """Reporter that delegates to multiple reporters.

    Allows using both ConsoleReporter and JsonReporter simultaneously.
    """

    def __init__(self, reporters: list[Reporter]):
        """Initialize with list of reporters.

        Args:
            reporters: List of reporters to delegate to
        """
        self._reporters = reporters

    def on_case_start(self, provider_name: str, case_id: str) -> None:
        """Delegate to all reporters."""
        for reporter in self._reporters:
            reporter.on_case_start(provider_name, case_id)

    def on_case_complete(self, provider_name: str, result) -> None:
        """Delegate to all reporters."""
        for reporter in self._reporters:
            reporter.on_case_complete(provider_name, result)

    def on_provider_start(self, provider_name: str) -> None:
        """Delegate to all reporters."""
        for reporter in self._reporters:
            reporter.on_provider_start(provider_name)

    def on_provider_complete(self, result) -> None:
        """Delegate to all reporters."""
        for reporter in self._reporters:
            reporter.on_provider_complete(result)

    def on_run_complete(self, results: dict) -> None:
        """Delegate to all reporters."""
        for reporter in self._reporters:
            reporter.on_run_complete(results)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        prog="s3-enforcement-tester",
        description="Test S3-compatible providers for Content-Length enforcement",
    )

    parser.add_argument(
        "-c", "--config",
        default="config.json",
        help="Path to configuration file (default: config.json)",
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress per-case output, show only summary",
    )

    parser.add_argument(
        "-j", "--json-output",
        metavar="PATH",
        help="Write JSON results to file",
    )

    parser.add_argument(
        "-p", "--providers",
        metavar="LIST",
        help="Comma-separated list of provider keys to test",
    )

    parser.add_argument(
        "--github-actions",
        action="store_true",
        help="Enable GitHub Actions output mode",
    )

    parser.add_argument(
        "--build-site",
        action="store_true",
        help="Generate site artifacts after tests (badges, history, etc.)",
    )

    parser.add_argument(
        "--site-dir",
        metavar="DIR",
        default="site/data",
        help="Output directory for site data (default: site/data)",
    )

    return parser.parse_args(argv)


def create_reporters(args: argparse.Namespace) -> list[Reporter]:
    """Create reporters based on command-line arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        List of configured reporters
    """
    reporters = []

    # Always add console reporter
    reporters.append(ConsoleReporter(quiet=args.quiet))

    # Add JSON reporter if requested
    if args.json_output or args.github_actions:
        reporters.append(JsonReporter(
            output_path=args.json_output,
            github_output=args.github_actions,
        ))

    return reporters


def filter_providers(
    providers: dict[str, ProviderConfig],
    filter_str: str,
) -> dict[str, ProviderConfig]:
    """Filter providers by comma-separated key list.

    Args:
        providers: All available providers
        filter_str: Comma-separated list of keys to include

    Returns:
        Filtered dictionary of providers
    """
    keys = [k.strip() for k in filter_str.split(",")]
    return {k: v for k, v in providers.items() if k in keys}


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code: 0 for success, 1 for test failures, 2 for errors
    """
    args = parse_args(argv)

    # Load configuration
    try:
        providers = load_providers(args.config)
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2

    # Filter providers if requested
    if args.providers:
        providers = filter_providers(providers, args.providers)
        if not providers:
            print("No matching providers found", file=sys.stderr)
            return 2

    # Create reporters
    reporters = create_reporters(args)
    if len(reporters) == 1:
        reporter = reporters[0]
    else:
        reporter = CompositeReporter(reporters)

    # Run tests
    runner = EnforcementRunner(providers, reporter=reporter)
    result = runner.run()

    # Build site if requested
    if args.build_site:
        try:
            build_site(result.to_dict(), args.site_dir)
            print(f"Site artifacts written to: {args.site_dir}")
        except SiteGeneratorError as e:
            print(f"Site generation error: {e}", file=sys.stderr)
            return 2

    # Return appropriate exit code
    return 0 if result.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
