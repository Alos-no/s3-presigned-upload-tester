"""Test case definitions and execution logic for S3 enforcement testing.

This module contains:
- CASE_DEFINITIONS: Test cases for Content-Length enforcement
  - Multipart upload tests (case_1, case_2, case_5-8)
  - Single-part upload tests (case_9-12)
- Data generators for creating test payloads
- CaseExecutor: Orchestrates running test cases against a provider
"""

import random
from dataclasses import dataclass
from typing import Any, Generator, Optional

import httpx
from h11 import LocalProtocolError as H11LocalProtocolError

from src.models import ProviderConfig

# Test object keys used for tests
TEST_OBJECT_KEY = "e2e-multipart-test.bin"
SINGLE_PART_TEST_KEY = "e2e-single-part-test.bin"

# Test case definitions
# Multipart upload tests (case_1, case_2, case_5-8)
# Note: case_3 (Body Truncated) and case_4 (Body Extended) were consolidated
# into case_1 and case_2 as they test the same enforcement (CL vs body mismatch)
#
# Single-part upload tests (case_9-12)
# These test presigned PutObject URLs (non-multipart uploads)
CASE_DEFINITIONS = {
    # === MULTIPART UPLOAD TESTS ===
    "case_1": {
        "id": "case_1",
        "name": "Content-Length Header > Body Size",
        "description": "Header claims more data than is sent. Server must reject.",
        "expect_failure": True,
        "upload_type": "multipart",
    },
    "case_2": {
        "id": "case_2",
        "name": "Content-Length Header < Body Size",
        "description": "Header claims less data than is sent. Server must reject or truncate.",
        "expect_failure": True,
        "upload_type": "multipart",
    },
    "case_5": {
        "id": "case_5",
        "name": "Body > Signed Content-Length",
        "description": "CRITICAL: Body and header match but exceed signed value. Signature enforcement MUST reject.",
        "expect_failure": True,
        "upload_type": "multipart",
    },
    "case_6": {
        "id": "case_6",
        "name": "Body < Signed Content-Length",
        "description": "Body and header match but are smaller than signed value. Signature enforcement MUST reject.",
        "expect_failure": True,
        "upload_type": "multipart",
    },
    "case_7": {
        "id": "case_7",
        "name": "Control Group (Valid Request)",
        "description": "Correct body matching header and signature. MUST succeed.",
        "expect_failure": False,
        "upload_type": "multipart",
    },
    "case_8": {
        "id": "case_8",
        "name": "List Parts API Verification",
        "description": "Verify provider accurately reports uploaded parts.",
        "expect_failure": False,
        "upload_type": "multipart",
    },
    # === SINGLE-PART UPLOAD TESTS ===
    "case_9": {
        "id": "case_9",
        "name": "Single-Part: CL Header > Body",
        "description": "Single-part upload where header claims more data than sent. Server must reject.",
        "expect_failure": True,
        "upload_type": "single",
    },
    "case_10": {
        "id": "case_10",
        "name": "Single-Part: CL Header < Body",
        "description": "Single-part upload where header claims less data than sent. Server must reject or truncate.",
        "expect_failure": True,
        "upload_type": "single",
    },
    "case_11": {
        "id": "case_11",
        "name": "Single-Part: Body > Signed CL",
        "description": "Single-part upload where body exceeds signed Content-Length. Signature enforcement MUST reject.",
        "expect_failure": True,
        "upload_type": "single",
    },
    "case_12": {
        "id": "case_12",
        "name": "Single-Part: Control (Valid)",
        "description": "Single-part upload with correct body matching header and signature. MUST succeed.",
        "expect_failure": False,
        "upload_type": "single",
    },
}

# Helper constants for categorizing tests
MULTIPART_UPLOAD_CASES = ["case_1", "case_2", "case_5", "case_6", "case_7"]
SINGLE_PART_UPLOAD_CASES = ["case_9", "case_10", "case_11", "case_12"]
LIST_PARTS_CASE = "case_8"


@dataclass
class CaseExecutionResult:
    """Result of executing a single test case."""

    case_id: str
    passed: bool
    expected_failure: bool
    actual_status_code: Optional[int] = None
    error_message: Optional[str] = None
    etag: Optional[str] = None


def single_chunk_generator(data: bytes) -> Generator[bytes, None, None]:
    """Generator that yields the provided data chunk a single time."""
    yield data


def truncated_chunk_generator(data: bytes) -> Generator[bytes, None, None]:
    """Generator that yields everything except the last byte."""
    yield data[:-1]


def extended_chunk_generator(data: bytes) -> Generator[bytes, None, None]:
    """Generator that yields original data plus one extra random byte."""
    yield data + random.randbytes(1)


class CaseExecutor:
    """Executes test cases against an S3-compatible provider.

    This class handles:
    - Generating presigned URLs for part uploads
    - Preparing test case data (body and headers)
    - Executing HTTP requests against presigned URLs
    - Evaluating results against expected outcomes
    """

    def __init__(
        self,
        http_client: httpx.Client,
        s3_client: Any,
        config: ProviderConfig,
    ):
        """Initialize the executor.

        Args:
            http_client: httpx client for HTTP requests
            s3_client: boto3 S3 client for presigned URL generation
            config: Provider configuration
        """
        self.http_client = http_client
        self.s3_client = s3_client
        self.config = config

    def generate_presigned_url(
        self,
        upload_id: str,
        part_number: int,
        content_length: int,
    ) -> str:
        """Generate a presigned URL for uploading a part (multipart).

        The Content-Length is signed into the URL, which is the key to
        the enforcement mechanism being tested.

        Args:
            upload_id: The multipart upload ID
            part_number: The part number (1-based)
            content_length: The expected content length to sign

        Returns:
            The presigned URL for uploading the part
        """
        return self.s3_client.generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": self.config.bucket_name,
                "Key": TEST_OBJECT_KEY,
                "UploadId": upload_id,
                "PartNumber": part_number,
                "ContentLength": content_length,
            },
            ExpiresIn=3600,
            HttpMethod="PUT",
        )

    def generate_single_part_presigned_url(
        self,
        content_length: int,
        object_key: str = SINGLE_PART_TEST_KEY,
    ) -> str:
        """Generate a presigned URL for a single-part (non-multipart) upload.

        The Content-Length is signed into the URL, which is the key to
        the enforcement mechanism being tested.

        Args:
            content_length: The expected content length to sign
            object_key: The object key (defaults to SINGLE_PART_TEST_KEY)

        Returns:
            The presigned URL for the single-part upload
        """
        return self.s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.config.bucket_name,
                "Key": object_key,
                "ContentLength": content_length,
            },
            ExpiresIn=3600,
            HttpMethod="PUT",
        )

    def prepare_case_data(
        self,
        case_id: str,
        chunk_data: bytes,
    ) -> tuple[Generator[bytes, None, None], dict[str, str]]:
        """Prepare data generator and headers for a specific test case.

        Args:
            case_id: The test case identifier
            chunk_data: The reference chunk data (what the URL was signed for)

        Returns:
            Tuple of (data_generator, headers_dict)
        """
        correct_size = len(chunk_data)

        # === MULTIPART UPLOAD CASES ===
        if case_id == "case_1":
            # Header claims more than body (body is truncated)
            return truncated_chunk_generator(chunk_data), {"Content-Length": str(correct_size)}

        elif case_id == "case_2":
            # Header claims less than body (body is extended)
            return extended_chunk_generator(chunk_data), {"Content-Length": str(correct_size)}

        elif case_id == "case_5":
            # Body and header match, but larger than signed value
            extended_data = chunk_data + random.randbytes(1)
            return single_chunk_generator(extended_data), {"Content-Length": str(correct_size + 1)}

        elif case_id == "case_6":
            # Body and header match, but smaller than signed value
            truncated_data = chunk_data[:-1]
            return single_chunk_generator(truncated_data), {"Content-Length": str(correct_size - 1)}

        elif case_id == "case_7":
            # Control group: everything matches
            return single_chunk_generator(chunk_data), {"Content-Length": str(correct_size)}

        # === SINGLE-PART UPLOAD CASES ===
        elif case_id == "case_9":
            # Single-part: Header claims more than body (body is truncated)
            return truncated_chunk_generator(chunk_data), {"Content-Length": str(correct_size)}

        elif case_id == "case_10":
            # Single-part: Header claims less than body (body is extended)
            return extended_chunk_generator(chunk_data), {"Content-Length": str(correct_size)}

        elif case_id == "case_11":
            # Single-part: Body and header match, but larger than signed value
            extended_data = chunk_data + random.randbytes(1)
            return single_chunk_generator(extended_data), {"Content-Length": str(correct_size + 1)}

        elif case_id == "case_12":
            # Single-part: Control group - everything matches
            return single_chunk_generator(chunk_data), {"Content-Length": str(correct_size)}

        else:
            raise ValueError(f"Unknown case_id: {case_id}")

    def run_upload_case(
        self,
        case_id: str,
        presigned_url: str,
        chunk_data: bytes,
    ) -> CaseExecutionResult:
        """Execute a single upload test case.

        Args:
            case_id: The test case to run (case_1 through case_7)
            presigned_url: The presigned URL for the upload
            chunk_data: The reference chunk data

        Returns:
            CaseExecutionResult with pass/fail status and details
        """
        case_def = CASE_DEFINITIONS.get(case_id)
        if not case_def:
            raise ValueError(f"Unknown case_id: {case_id}")

        expect_failure = case_def["expect_failure"]
        data_gen, headers = self.prepare_case_data(case_id, chunk_data)

        try:
            response = self.http_client.put(
                presigned_url,
                content=data_gen,
                headers=headers,
            )
            response.raise_for_status()

            # Request succeeded
            if not expect_failure:
                # Success was expected - PASS
                return CaseExecutionResult(
                    case_id=case_id,
                    passed=True,
                    expected_failure=False,
                    actual_status_code=response.status_code,
                    etag=response.headers.get("ETag"),
                )
            else:
                # We expected failure but got success - FAIL (security risk)
                return CaseExecutionResult(
                    case_id=case_id,
                    passed=False,
                    expected_failure=True,
                    actual_status_code=response.status_code,
                    error_message="Provider incorrectly accepted invalid request",
                )

        except (httpx.LocalProtocolError, H11LocalProtocolError, httpx.HTTPError) as e:
            # Request failed (client-side validation, network error, or HTTP error)
            status_code = None
            if isinstance(e, httpx.HTTPStatusError):
                status_code = e.response.status_code

            if expect_failure:
                # Failure was expected - PASS
                return CaseExecutionResult(
                    case_id=case_id,
                    passed=True,
                    expected_failure=True,
                    actual_status_code=status_code,
                )
            else:
                # We expected success but got failure - FAIL
                return CaseExecutionResult(
                    case_id=case_id,
                    passed=False,
                    expected_failure=False,
                    actual_status_code=status_code,
                    error_message=str(e),
                )

        except Exception as e:
            # Unexpected error
            return CaseExecutionResult(
                case_id=case_id,
                passed=False,
                expected_failure=expect_failure,
                error_message=f"Unexpected error: {e}",
            )

    def run_list_parts_test(
        self,
        upload_id: str,
        expected_parts: list[dict],
    ) -> CaseExecutionResult:
        """Execute the List Parts API test (case_8).

        Args:
            upload_id: The multipart upload ID
            expected_parts: List of expected parts with PartNumber and ETag

        Returns:
            CaseExecutionResult with pass/fail status
        """
        try:
            response = self.s3_client.list_parts(
                Bucket=self.config.bucket_name,
                Key=TEST_OBJECT_KEY,
                UploadId=upload_id,
            )

            provider_parts = response.get("Parts", [])

            # Check part count
            if len(provider_parts) != len(expected_parts):
                return CaseExecutionResult(
                    case_id="case_8",
                    passed=False,
                    expected_failure=False,
                    error_message=f"Part count mismatch: expected {len(expected_parts)}, got {len(provider_parts)}",
                )

            # Check each part's ETag
            provider_parts_dict = {p["PartNumber"]: p["ETag"] for p in provider_parts}
            for expected_part in expected_parts:
                part_num = expected_part["PartNumber"]
                expected_etag = expected_part["ETag"]

                if part_num not in provider_parts_dict:
                    return CaseExecutionResult(
                        case_id="case_8",
                        passed=False,
                        expected_failure=False,
                        error_message=f"Part {part_num} not found in provider response",
                    )

                if provider_parts_dict[part_num] != expected_etag:
                    return CaseExecutionResult(
                        case_id="case_8",
                        passed=False,
                        expected_failure=False,
                        error_message=f"ETag mismatch for part {part_num}: expected {expected_etag}, got {provider_parts_dict[part_num]}",
                    )

            # All checks passed
            return CaseExecutionResult(
                case_id="case_8",
                passed=True,
                expected_failure=False,
            )

        except Exception as e:
            return CaseExecutionResult(
                case_id="case_8",
                passed=False,
                expected_failure=False,
                error_message=f"List Parts API error: {e}",
            )

    def run_single_part_case(
        self,
        case_id: str,
        test_data: bytes,
    ) -> CaseExecutionResult:
        """Execute a single-part upload test case.

        This method generates the presigned URL and runs the test case.

        Args:
            case_id: The test case to run (case_9 through case_12)
            test_data: The reference data (what the URL will be signed for)

        Returns:
            CaseExecutionResult with pass/fail status and details
        """
        # Generate presigned URL for single-part upload
        presigned_url = self.generate_single_part_presigned_url(
            content_length=len(test_data),
        )

        # Reuse the upload case logic
        return self.run_upload_case(case_id, presigned_url, test_data)

    def cleanup_single_part_object(self, object_key: str = SINGLE_PART_TEST_KEY) -> None:
        """Delete the single-part test object if it exists.

        Args:
            object_key: The object key to delete (defaults to SINGLE_PART_TEST_KEY)
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.config.bucket_name,
                Key=object_key,
            )
        except Exception:
            # Ignore errors - object might not exist
            pass
