"""Main test runner and orchestrator.

Coordinates test execution across multiple providers, managing:
- Provider iteration
- Test file creation and cleanup
- S3 and HTTP client lifecycle
- Reporter callbacks
"""

import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from src.models import ProviderConfig, ProviderResult, CaseResult, ResultStatus
from src.s3_client import build_s3_client
from src.multipart import MultipartUpload, create_test_file, DEFAULT_CHUNK_SIZE
from src.test_cases import (
    CaseExecutor,
    CASE_DEFINITIONS,
    SINGLE_PART_UPLOAD_CASES,
)

# Size for single-part test data (1KB - small for quick tests)
SINGLE_PART_TEST_SIZE = 1024


@dataclass
class RunResult:
    """Result of running tests across all providers."""

    providers: dict[str, ProviderResult]
    total_duration: float
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    @property
    def all_passed(self) -> bool:
        """Check if all providers passed."""
        return all(p.status == ResultStatus.PASS for p in self.providers.values())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict matching the JSON output schema
        """
        providers_dict = {}
        for key, provider_result in self.providers.items():
            cases_dict = {}
            for case_id, case_result in provider_result.cases.items():
                cases_dict[case_id] = {
                    "status": case_result.status.value,
                    "expected": case_result.expected,
                    "actual": case_result.actual,
                    "error_message": case_result.error_message,
                }

            providers_dict[key] = {
                "name": provider_result.provider_name,
                "status": provider_result.status.value,
                "cases": cases_dict,
                "duration_seconds": provider_result.duration_seconds,
                "error_message": provider_result.error_message,
            }

        passed_count = sum(1 for p in self.providers.values() if p.status == ResultStatus.PASS)
        failed_count = sum(1 for p in self.providers.values() if p.status == ResultStatus.FAIL)

        return {
            "timestamp": self.timestamp,
            "providers": providers_dict,
            "summary": {
                "total_providers": len(self.providers),
                "passed": passed_count,
                "failed": failed_count,
            },
        }


class ProviderTestSession:
    """Manages a test session for a single provider.

    Encapsulates the clients and logic for running test cases
    against a specific provider.
    """

    def __init__(
        self,
        s3_client: Any,
        http_client: httpx.Client,
        config: ProviderConfig,
    ):
        """Initialize the test session.

        Args:
            s3_client: boto3 S3 client for this provider
            http_client: httpx client for HTTP requests
            config: Provider configuration
        """
        self.s3_client = s3_client
        self.http_client = http_client
        self.config = config
        self._executor = CaseExecutor(http_client, s3_client, config)

    def run_case_for_part(
        self,
        case_id: str,
        upload_id: str,
        part_number: int,
        chunk_data: bytes,
    ):
        """Run a single test case for a specific part.

        Args:
            case_id: The test case ID (case_1 through case_7)
            upload_id: The multipart upload ID
            part_number: The part number
            chunk_data: The chunk data to use

        Returns:
            CaseExecutionResult with the test outcome
        """
        presigned_url = self._executor.generate_presigned_url(
            upload_id=upload_id,
            part_number=part_number,
            content_length=len(chunk_data),
        )
        return self._executor.run_upload_case(
            case_id=case_id,
            presigned_url=presigned_url,
            chunk_data=chunk_data,
        )

    def run_all_cases_for_part(
        self,
        upload_id: str,
        part_number: int,
        chunk_data: bytes,
    ) -> list:
        """Run all upload test cases (1, 2, 5, 6, 7) for a part.

        Note: case_3 (Body Truncated) and case_4 (Body Extended) were
        consolidated into case_1 and case_2 as they test the same enforcement.

        Args:
            upload_id: The multipart upload ID
            part_number: The part number
            chunk_data: The chunk data to use

        Returns:
            List of CaseExecutionResult for each test case
        """
        results = []
        # Upload test cases: 1, 2, 5, 6, 7 (case_8 is list_parts, run separately)
        for case_id in ["case_1", "case_2", "case_5", "case_6", "case_7"]:
            presigned_url = self._executor.generate_presigned_url(
                upload_id=upload_id,
                part_number=part_number,
                content_length=len(chunk_data),
            )
            result = self._executor.run_upload_case(
                case_id=case_id,
                presigned_url=presigned_url,
                chunk_data=chunk_data,
            )
            results.append(result)
        return results

    def run_list_parts_test(
        self,
        upload_id: str,
        expected_parts: list[dict],
    ):
        """Run the list parts verification test.

        Args:
            upload_id: The multipart upload ID
            expected_parts: Expected parts list

        Returns:
            CaseExecutionResult for case_8
        """
        return self._executor.run_list_parts_test(
            upload_id=upload_id,
            expected_parts=expected_parts,
        )

    def run_all_single_part_cases(self, test_data: bytes) -> list:
        """Run all single-part upload test cases (case_9 through case_12).

        Args:
            test_data: The test data to use for uploads

        Returns:
            List of CaseExecutionResult for each test case
        """
        results = []
        for case_id in SINGLE_PART_UPLOAD_CASES:
            result = self._executor.run_single_part_case(case_id, test_data)
            results.append(result)
        return results

    def cleanup_single_part_objects(self) -> None:
        """Clean up any single-part test objects."""
        self._executor.cleanup_single_part_object()


class EnforcementRunner:
    """Main test runner that orchestrates test execution.

    Coordinates:
    - Iterating through configured providers
    - Creating and cleaning up test files
    - Managing S3 and HTTP client lifecycle
    - Calling reporter callbacks for progress
    """

    def __init__(
        self,
        providers: dict[str, ProviderConfig],
        reporter: Optional[Any] = None,
    ):
        """Initialize the test runner.

        Args:
            providers: Dictionary of provider configurations
            reporter: Optional reporter for progress callbacks
        """
        self.providers = providers
        self.reporter = reporter

    def run(self) -> RunResult:
        """Run tests for all configured providers.

        Returns:
            RunResult containing results for all providers
        """
        start_time = time.time()
        results: dict[str, ProviderResult] = {}

        # Create test file once for all providers
        test_file_path = create_test_file()

        try:
            for provider_key, config in self.providers.items():
                if self.reporter:
                    self.reporter.on_provider_start(config.provider_name)

                try:
                    result = self._run_provider_tests(config, test_file_path)
                except Exception as e:
                    result = ProviderResult(
                        provider_key=provider_key,
                        provider_name=config.provider_name,
                        status=ResultStatus.ERROR,
                        error_message=str(e),
                    )

                results[provider_key] = result

                if self.reporter:
                    self.reporter.on_provider_complete(result)

        finally:
            # Clean up test file
            if os.path.exists(test_file_path):
                os.remove(test_file_path)

        total_duration = time.time() - start_time
        run_result = RunResult(providers=results, total_duration=total_duration)

        if self.reporter:
            self.reporter.on_run_complete(results)

        return run_result

    def _run_provider_tests(
        self,
        config: ProviderConfig,
        test_file_path: str,
    ) -> ProviderResult:
        """Run all tests for a single provider.

        Args:
            config: Provider configuration
            test_file_path: Path to the test file

        Returns:
            ProviderResult with aggregated results
        """
        start_time = time.time()
        cases: dict[str, CaseResult] = {}
        overall_status = ResultStatus.PASS

        # Build clients
        s3_client = build_s3_client(config)
        http_client = httpx.Client(timeout=60.0)

        try:
            session = ProviderTestSession(s3_client, http_client, config)

            with MultipartUpload(s3_client, config) as upload:
                # Run tests for each part
                for part_number, chunk_data in upload.iterate_parts(test_file_path):
                    # Run all test cases for this part
                    case_results = session.run_all_cases_for_part(
                        upload_id=upload.upload_id,
                        part_number=part_number,
                        chunk_data=chunk_data,
                    )

                    # Process results
                    for exec_result in case_results:
                        case_def = CASE_DEFINITIONS.get(exec_result.case_id, {})
                        case_name = case_def.get("name", exec_result.case_id)

                        # Convert execution result to CaseResult
                        if exec_result.passed:
                            status = ResultStatus.PASS
                        else:
                            status = ResultStatus.FAIL
                            overall_status = ResultStatus.FAIL

                        # Store the result (aggregate across parts)
                        if exec_result.case_id not in cases or status == ResultStatus.FAIL:
                            cases[exec_result.case_id] = CaseResult(
                                case_id=exec_result.case_id,
                                case_name=case_name,
                                status=status,
                                expected="rejected" if exec_result.expected_failure else "accepted",
                                actual="rejected" if exec_result.actual_status_code in (None, 403, 400) else "accepted",
                                error_message=exec_result.error_message,
                            )

                        # If case 7 (control) passed, record the part
                        if exec_result.case_id == "case_7" and exec_result.passed:
                            upload.add_part(part_number, exec_result.etag)

                    # Run list parts test after each part
                    list_result = session.run_list_parts_test(
                        upload_id=upload.upload_id,
                        expected_parts=upload.get_uploaded_parts(),
                    )

                    if not list_result.passed:
                        overall_status = ResultStatus.FAIL

                    cases["case_8"] = CaseResult(
                        case_id="case_8",
                        case_name=CASE_DEFINITIONS["case_8"]["name"],
                        status=ResultStatus.PASS if list_result.passed else ResultStatus.FAIL,
                        expected="parts match",
                        actual="parts match" if list_result.passed else "mismatch",
                        error_message=list_result.error_message,
                    )

                    if self.reporter:
                        for case_id, case_result in cases.items():
                            self.reporter.on_case_complete(config.provider_name, case_result)

                # Complete the upload if all control tests passed
                if overall_status == ResultStatus.PASS:
                    upload.complete()

            # Cleanup remote object
            upload.cleanup_remote()

            # === RUN SINGLE-PART UPLOAD TESTS ===
            # Generate test data for single-part tests
            single_part_test_data = os.urandom(SINGLE_PART_TEST_SIZE)

            single_part_results = session.run_all_single_part_cases(single_part_test_data)

            for exec_result in single_part_results:
                case_def = CASE_DEFINITIONS.get(exec_result.case_id, {})
                case_name = case_def.get("name", exec_result.case_id)

                if exec_result.passed:
                    status = ResultStatus.PASS
                else:
                    status = ResultStatus.FAIL
                    overall_status = ResultStatus.FAIL

                cases[exec_result.case_id] = CaseResult(
                    case_id=exec_result.case_id,
                    case_name=case_name,
                    status=status,
                    expected="rejected" if exec_result.expected_failure else "accepted",
                    actual="rejected" if exec_result.actual_status_code in (None, 403, 400) else "accepted",
                    error_message=exec_result.error_message,
                )

                if self.reporter:
                    self.reporter.on_case_complete(config.provider_name, cases[exec_result.case_id])

            # Cleanup single-part test objects
            session.cleanup_single_part_objects()

        finally:
            http_client.close()

        duration = time.time() - start_time
        return ProviderResult(
            provider_key=config.key,
            provider_name=config.provider_name,
            status=overall_status,
            cases=cases,
            duration_seconds=duration,
        )
