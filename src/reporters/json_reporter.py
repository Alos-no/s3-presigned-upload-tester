"""JSON reporter for structured output and GitHub Actions integration.

Generates JSON output suitable for:
- GitHub Pages dashboard data
- GitHub Actions workflow outputs
- Historical data persistence
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.reporters.base import Reporter
from src.models import CaseResult, ProviderResult, ResultStatus


class JsonReporter(Reporter):
    """JSON reporter for structured output.

    Generates JSON data suitable for:
    - Dashboard visualization
    - GitHub Actions outputs
    - Historical data storage

    Args:
        output_path: Optional file path to write JSON output
        github_output: If True, write to GITHUB_OUTPUT for Actions
    """

    def __init__(
        self,
        output_path: Optional[str] = None,
        github_output: bool = False,
    ):
        """Initialize the JSON reporter.

        Args:
            output_path: File path for JSON output (optional)
            github_output: Enable GitHub Actions output
        """
        self.output_path = output_path
        self.github_output = github_output
        self._results: list[ProviderResult] = []

    def on_case_start(self, provider_name: str, case_id: str) -> None:
        """Called when a test case starts. No-op for JSON reporter."""
        pass

    def on_case_complete(self, provider_name: str, result: CaseResult) -> None:
        """Called when a test case completes. No-op - data comes from provider."""
        pass

    def on_provider_start(self, provider_name: str) -> None:
        """Called when testing begins for a provider. No-op for JSON reporter."""
        pass

    def on_provider_complete(self, result: ProviderResult) -> None:
        """Called when testing completes for a provider.

        Stores the result for final output generation.
        """
        self._results.append(result)

    def on_run_complete(self, results: dict[str, ProviderResult]) -> dict:
        """Called when all testing is complete.

        Generates and outputs JSON data.

        Args:
            results: Dictionary of provider results

        Returns:
            The generated JSON data as a dictionary
        """
        output = self._generate_output(results)

        # Write to file if path provided
        if self.output_path:
            self._write_to_file(output)

        # Write GitHub Actions output if enabled
        if self.github_output:
            self._write_github_output(output)

        return output

    def _generate_output(self, results: dict[str, ProviderResult]) -> dict:
        """Generate the JSON output structure.

        Args:
            results: Dictionary of provider results

        Returns:
            Structured dictionary for JSON output
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Build provider data
        providers = {}
        passed_count = 0
        failed_count = 0
        error_count = 0

        for provider_key, provider_result in results.items():
            # Count statuses
            if provider_result.status == ResultStatus.PASS:
                passed_count += 1
            elif provider_result.status == ResultStatus.FAIL:
                failed_count += 1
            else:
                error_count += 1

            # Build case data
            cases = {}
            for case_id, case_result in provider_result.cases.items():
                case_data = {
                    "status": case_result.status.value,
                    "expected": case_result.expected,
                    "actual": case_result.actual,
                }
                if case_result.error_message:
                    case_data["error"] = case_result.error_message
                cases[case_id] = case_data

            providers[provider_key] = {
                "name": provider_result.provider_name,
                "status": provider_result.status.value,
                "cases": cases,
                "duration_seconds": provider_result.duration_seconds,
            }

            if provider_result.error_message:
                providers[provider_key]["error"] = provider_result.error_message

        # Build summary
        total = len(results)
        all_passed = passed_count == total and total > 0

        return {
            "timestamp": timestamp,
            "providers": providers,
            "summary": {
                "total_providers": total,
                "passed": passed_count,
                "failed": failed_count,
                "errors": error_count,
                "all_passed": all_passed,
            },
        }

    def _write_to_file(self, output: dict) -> None:
        """Write JSON output to file.

        Args:
            output: The data to write
        """
        path = Path(self.output_path)

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.output_path, "w") as f:
            json.dump(output, f, indent=2)

    def _write_github_output(self, output: dict) -> None:
        """Write to GitHub Actions output file.

        Args:
            output: The data to write
        """
        github_output_file = os.environ.get("GITHUB_OUTPUT")
        if not github_output_file:
            return

        with open(github_output_file, "a") as f:
            # Write summary values as outputs
            f.write(f"all_passed={str(output['summary']['all_passed']).lower()}\n")
            f.write(f"total_providers={output['summary']['total_providers']}\n")
            f.write(f"passed_providers={output['summary']['passed']}\n")
            f.write(f"failed_providers={output['summary']['failed']}\n")

            # Write full JSON as multiline output
            f.write("results<<EOF\n")
            f.write(json.dumps(output))
            f.write("\nEOF\n")
