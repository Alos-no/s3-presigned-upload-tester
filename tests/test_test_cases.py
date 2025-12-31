"""Tests for test_cases.py module.

Tests the test case definitions, data generators, and execution logic.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import httpx
from h11 import LocalProtocolError as H11LocalProtocolError

from src.test_cases import (
    CASE_DEFINITIONS,
    single_chunk_generator,
    truncated_chunk_generator,
    extended_chunk_generator,
    CaseExecutor,
    CaseExecutionResult,
)
from src.models import ProviderConfig


class TestCaseDefinitions:
    """Tests for case definition constants."""

    def test_case_definitions_exist(self):
        """All 10 test cases should be defined (6 multipart + 4 single-part)."""
        assert len(CASE_DEFINITIONS) == 10

    def test_all_cases_have_required_fields(self):
        """Each case should have id, name, description, expect_failure."""
        required_fields = {"id", "name", "description", "expect_failure"}
        for case_id, case_def in CASE_DEFINITIONS.items():
            assert required_fields.issubset(case_def.keys()), f"Case {case_id} missing fields"

    def test_case_1_expects_failure(self):
        """Case 1 (Content-Length > Body) should expect failure."""
        assert CASE_DEFINITIONS["case_1"]["expect_failure"] is True
        assert "Content-Length" in CASE_DEFINITIONS["case_1"]["name"]

    def test_case_2_expects_failure(self):
        """Case 2 (Content-Length < Body) should expect failure."""
        assert CASE_DEFINITIONS["case_2"]["expect_failure"] is True

    def test_case_5_expects_failure(self):
        """Case 5 (Signed < Actual) should expect failure - signature enforcement."""
        assert CASE_DEFINITIONS["case_5"]["expect_failure"] is True

    def test_case_6_expects_failure(self):
        """Case 6 (Signed > Actual) should expect failure - signature enforcement."""
        assert CASE_DEFINITIONS["case_6"]["expect_failure"] is True

    def test_case_7_expects_success(self):
        """Case 7 (Control Group) should expect success."""
        assert CASE_DEFINITIONS["case_7"]["expect_failure"] is False

    def test_case_8_is_list_parts(self):
        """Case 8 should be the List Parts API test."""
        assert "list" in CASE_DEFINITIONS["case_8"]["name"].lower()
        assert "parts" in CASE_DEFINITIONS["case_8"]["name"].lower()

    def test_case_9_single_part_cl_greater(self):
        """Case 9 (Single-Part: CL Header > Body) should expect failure."""
        assert CASE_DEFINITIONS["case_9"]["expect_failure"] is True
        assert CASE_DEFINITIONS["case_9"]["upload_type"] == "single"

    def test_case_10_single_part_cl_less(self):
        """Case 10 (Single-Part: CL Header < Body) should expect failure."""
        assert CASE_DEFINITIONS["case_10"]["expect_failure"] is True
        assert CASE_DEFINITIONS["case_10"]["upload_type"] == "single"

    def test_case_11_single_part_body_greater_signed(self):
        """Case 11 (Single-Part: Body > Signed CL) should expect failure."""
        assert CASE_DEFINITIONS["case_11"]["expect_failure"] is True
        assert CASE_DEFINITIONS["case_11"]["upload_type"] == "single"

    def test_case_12_single_part_control(self):
        """Case 12 (Single-Part: Control) should expect success."""
        assert CASE_DEFINITIONS["case_12"]["expect_failure"] is False
        assert CASE_DEFINITIONS["case_12"]["upload_type"] == "single"


class TestDataGenerators:
    """Tests for data stream generators."""

    def test_single_chunk_generator_yields_exact_data(self):
        """single_chunk_generator should yield data unchanged."""
        data = b"test data 12345"
        result = b"".join(single_chunk_generator(data))
        assert result == data

    def test_single_chunk_generator_yields_once(self):
        """single_chunk_generator should yield exactly once."""
        data = b"test"
        gen = single_chunk_generator(data)
        chunks = list(gen)
        assert len(chunks) == 1

    def test_truncated_chunk_generator_removes_last_byte(self):
        """truncated_chunk_generator should yield data minus the last byte."""
        data = b"test data"
        result = b"".join(truncated_chunk_generator(data))
        assert result == b"test dat"
        assert len(result) == len(data) - 1

    def test_truncated_chunk_generator_with_single_byte(self):
        """truncated_chunk_generator with single byte yields empty."""
        data = b"x"
        result = b"".join(truncated_chunk_generator(data))
        assert result == b""

    def test_extended_chunk_generator_adds_one_byte(self):
        """extended_chunk_generator should add one extra byte."""
        data = b"test data"
        result = b"".join(extended_chunk_generator(data))
        assert len(result) == len(data) + 1
        assert result.startswith(data)

    def test_extended_chunk_generator_yields_once(self):
        """extended_chunk_generator should yield exactly once."""
        data = b"test"
        gen = extended_chunk_generator(data)
        chunks = list(gen)
        assert len(chunks) == 1


class TestCaseExecutionResult:
    """Tests for CaseExecutionResult dataclass."""

    def test_create_pass_result(self):
        """Should create a passing result."""
        result = CaseExecutionResult(
            case_id="case_1",
            passed=True,
            expected_failure=True,
            actual_status_code=403,
        )
        assert result.case_id == "case_1"
        assert result.passed is True
        assert result.expected_failure is True
        assert result.actual_status_code == 403
        assert result.error_message is None

    def test_create_fail_result_with_error(self):
        """Should create a failing result with error message."""
        result = CaseExecutionResult(
            case_id="case_7",
            passed=False,
            expected_failure=False,
            actual_status_code=500,
            error_message="Server error",
        )
        assert result.passed is False
        assert result.error_message == "Server error"

    def test_etag_field_optional(self):
        """ETag should be optional and default to None."""
        result = CaseExecutionResult(
            case_id="case_7",
            passed=True,
            expected_failure=False,
            actual_status_code=200,
        )
        assert result.etag is None

    def test_etag_can_be_set(self):
        """ETag should be settable for control group tests."""
        result = CaseExecutionResult(
            case_id="case_7",
            passed=True,
            expected_failure=False,
            actual_status_code=200,
            etag='"abc123"',
        )
        assert result.etag == '"abc123"'


class TestCaseExecutorClass:
    """Tests for the CaseExecutor class."""

    @pytest.fixture
    def mock_http_client(self):
        """Create a mock httpx client."""
        return Mock(spec=httpx.Client)

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock boto3 S3 client."""
        client = Mock()
        client.generate_presigned_url.return_value = "https://example.com/presigned"
        return client

    @pytest.fixture
    def provider_config(self):
        """Create a test provider configuration."""
        return ProviderConfig(
            key="test",
            provider_name="Test Provider",
            endpoint_url="https://test.example.com",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="us-east-1",
            bucket_name="test-bucket",
        )

    @pytest.fixture
    def executor(self, mock_http_client, mock_s3_client, provider_config):
        """Create a CaseExecutor instance."""
        return CaseExecutor(
            http_client=mock_http_client,
            s3_client=mock_s3_client,
            config=provider_config,
        )

    def test_executor_initialization(self, executor, mock_http_client, mock_s3_client):
        """Executor should store clients and config."""
        assert executor.http_client is mock_http_client
        assert executor.s3_client is mock_s3_client
        assert executor.config.provider_name == "Test Provider"

    def test_generate_presigned_url(self, executor, mock_s3_client):
        """Should generate presigned URL with correct parameters."""
        url = executor.generate_presigned_url(
            upload_id="upload-123",
            part_number=1,
            content_length=5000,
        )

        mock_s3_client.generate_presigned_url.assert_called_once()
        call_args = mock_s3_client.generate_presigned_url.call_args
        assert call_args[0][0] == "upload_part"
        params = call_args[1]["Params"]
        assert params["UploadId"] == "upload-123"
        assert params["PartNumber"] == 1
        assert params["ContentLength"] == 5000
        assert url == "https://example.com/presigned"

    def test_generate_single_part_presigned_url(self, executor, mock_s3_client):
        """Should generate presigned URL for single-part (PutObject) upload."""
        mock_s3_client.generate_presigned_url.reset_mock()
        url = executor.generate_single_part_presigned_url(
            content_length=5000,
        )

        mock_s3_client.generate_presigned_url.assert_called_once()
        call_args = mock_s3_client.generate_presigned_url.call_args
        assert call_args[0][0] == "put_object"
        params = call_args[1]["Params"]
        assert params["ContentLength"] == 5000
        assert "Key" in params
        assert "Bucket" in params
        assert url == "https://example.com/presigned"

    def test_cleanup_single_part_object(self, executor, mock_s3_client):
        """Should attempt to delete single-part test object."""
        executor.cleanup_single_part_object()

        mock_s3_client.delete_object.assert_called_once()
        call_args = mock_s3_client.delete_object.call_args
        assert call_args[1]["Bucket"] == "test-bucket"

    def test_cleanup_single_part_object_handles_errors(self, executor, mock_s3_client):
        """Should handle errors gracefully when object doesn't exist."""
        mock_s3_client.delete_object.side_effect = Exception("Not Found")

        # Should not raise
        executor.cleanup_single_part_object()

    def test_run_case_1_header_larger_than_body(self, executor, mock_http_client):
        """Case 1: Content-Length header > actual body - should expect rejection."""
        # Mock a 403 response (signature mismatch)
        mock_response = Mock()
        mock_response.status_code = 403
        mock_http_client.put.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=Mock(), response=mock_response
        )

        chunk_data = b"x" * 1000
        result = executor.run_upload_case(
            case_id="case_1",
            presigned_url="https://example.com/presigned",
            chunk_data=chunk_data,
        )

        # Case 1 expects failure - if we get a 4xx, that's a PASS
        assert result.case_id == "case_1"
        assert result.passed is True
        assert result.expected_failure is True

    def test_run_case_7_control_group_success(self, executor, mock_http_client):
        """Case 7: Control group - should succeed with valid request."""
        # Mock a successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"ETag": '"etag123"'}
        mock_response.raise_for_status = Mock()
        mock_http_client.put.return_value = mock_response

        chunk_data = b"x" * 1000
        result = executor.run_upload_case(
            case_id="case_7",
            presigned_url="https://example.com/presigned",
            chunk_data=chunk_data,
        )

        assert result.case_id == "case_7"
        assert result.passed is True
        assert result.expected_failure is False
        assert result.etag == '"etag123"'

    def test_run_case_7_control_group_failure(self, executor, mock_http_client):
        """Case 7: If control group fails, test should fail."""
        # Mock a failure response
        mock_response = Mock()
        mock_response.status_code = 403
        mock_http_client.put.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=Mock(), response=mock_response
        )

        chunk_data = b"x" * 1000
        result = executor.run_upload_case(
            case_id="case_7",
            presigned_url="https://example.com/presigned",
            chunk_data=chunk_data,
        )

        # Control group expects success - if we get failure, that's a FAIL
        assert result.passed is False

    def test_run_case_5_signature_enforcement(self, executor, mock_http_client):
        """Case 5: Body > Signed Content-Length - critical signature test."""
        # Should be rejected due to signature mismatch
        mock_response = Mock()
        mock_response.status_code = 403
        mock_http_client.put.side_effect = httpx.HTTPStatusError(
            "Signature mismatch", request=Mock(), response=mock_response
        )

        chunk_data = b"x" * 1000
        result = executor.run_upload_case(
            case_id="case_5",
            presigned_url="https://example.com/presigned",
            chunk_data=chunk_data,
        )

        assert result.passed is True  # Rejection is expected
        assert result.expected_failure is True

    def test_run_case_handles_connection_error(self, executor, mock_http_client):
        """Should handle connection errors gracefully."""
        mock_http_client.put.side_effect = httpx.ConnectError("Connection failed")

        chunk_data = b"x" * 1000
        result = executor.run_upload_case(
            case_id="case_7",
            presigned_url="https://example.com/presigned",
            chunk_data=chunk_data,
        )

        # Control group failure due to connection error
        assert result.passed is False
        assert result.error_message is not None

    def test_run_case_handles_h11_local_protocol_error_expected_failure(
        self, executor, mock_http_client
    ):
        """h11.LocalProtocolError should be treated as expected failure for cases 1-4.

        This is the ACTUAL exception raised when httpx detects content-length mismatch
        at the client level (e.g., body size != Content-Length header).
        """
        # This is exactly what happens in real execution for cases 1-4
        mock_http_client.put.side_effect = H11LocalProtocolError(
            "Too little data for declared Content-Length"
        )

        chunk_data = b"x" * 1000
        result = executor.run_upload_case(
            case_id="case_1",  # Content-Length > Body - expects failure
            presigned_url="https://example.com/presigned",
            chunk_data=chunk_data,
        )

        # Case 1 expects failure - h11 error means request was rejected
        assert result.passed is True
        assert result.expected_failure is True

    def test_run_case_handles_h11_too_much_data_error(self, executor, mock_http_client):
        """h11.LocalProtocolError for 'too much data' should be handled."""
        mock_http_client.put.side_effect = H11LocalProtocolError(
            "Too much data for declared Content-Length"
        )

        chunk_data = b"x" * 1000
        result = executor.run_upload_case(
            case_id="case_2",  # Content-Length < Body - expects failure
            presigned_url="https://example.com/presigned",
            chunk_data=chunk_data,
        )

        assert result.passed is True
        assert result.expected_failure is True

    def test_run_case_h11_error_on_control_group_is_failure(
        self, executor, mock_http_client
    ):
        """h11.LocalProtocolError on control group (case_7) should fail the test."""
        mock_http_client.put.side_effect = H11LocalProtocolError(
            "Unexpected protocol error"
        )

        chunk_data = b"x" * 1000
        result = executor.run_upload_case(
            case_id="case_7",  # Control group - expects success
            presigned_url="https://example.com/presigned",
            chunk_data=chunk_data,
        )

        # Control group expects success - any error is a failure
        assert result.passed is False
        assert result.expected_failure is False

    def test_run_case_handles_httpx_local_protocol_error(
        self, executor, mock_http_client
    ):
        """httpx.LocalProtocolError should also be handled (different from h11)."""
        mock_http_client.put.side_effect = httpx.LocalProtocolError(
            "Protocol violation"
        )

        chunk_data = b"x" * 1000
        result = executor.run_upload_case(
            case_id="case_1",  # CL > Body - expects failure
            presigned_url="https://example.com/presigned",
            chunk_data=chunk_data,
        )

        assert result.passed is True
        assert result.expected_failure is True

    def test_run_list_parts_test_success(self, executor, mock_s3_client):
        """List Parts test should pass when parts match expectation."""
        mock_s3_client.list_parts.return_value = {
            "Parts": [
                {"PartNumber": 1, "ETag": '"etag1"'},
                {"PartNumber": 2, "ETag": '"etag2"'},
            ]
        }

        expected_parts = [
            {"PartNumber": 1, "ETag": '"etag1"'},
            {"PartNumber": 2, "ETag": '"etag2"'},
        ]

        result = executor.run_list_parts_test(
            upload_id="upload-123",
            expected_parts=expected_parts,
        )

        assert result.case_id == "case_8"
        assert result.passed is True

    def test_run_list_parts_test_count_mismatch(self, executor, mock_s3_client):
        """List Parts should fail when part count doesn't match."""
        mock_s3_client.list_parts.return_value = {
            "Parts": [{"PartNumber": 1, "ETag": '"etag1"'}]
        }

        expected_parts = [
            {"PartNumber": 1, "ETag": '"etag1"'},
            {"PartNumber": 2, "ETag": '"etag2"'},
        ]

        result = executor.run_list_parts_test(
            upload_id="upload-123",
            expected_parts=expected_parts,
        )

        assert result.passed is False
        assert "count" in result.error_message.lower() or "mismatch" in result.error_message.lower()

    def test_run_list_parts_test_etag_mismatch(self, executor, mock_s3_client):
        """List Parts should fail when ETags don't match."""
        mock_s3_client.list_parts.return_value = {
            "Parts": [{"PartNumber": 1, "ETag": '"wrong-etag"'}]
        }

        expected_parts = [{"PartNumber": 1, "ETag": '"correct-etag"'}]

        result = executor.run_list_parts_test(
            upload_id="upload-123",
            expected_parts=expected_parts,
        )

        assert result.passed is False
        assert "etag" in result.error_message.lower()

    def test_run_list_parts_test_api_error(self, executor, mock_s3_client):
        """List Parts should handle API errors gracefully."""
        mock_s3_client.list_parts.side_effect = Exception("API error")

        result = executor.run_list_parts_test(
            upload_id="upload-123",
            expected_parts=[],
        )

        assert result.passed is False
        assert result.error_message is not None


class TestCaseDataPreparation:
    """Tests for how each case prepares its data and headers."""

    @pytest.fixture
    def executor(self):
        """Create a minimal executor for data prep tests."""
        return CaseExecutor(
            http_client=Mock(spec=httpx.Client),
            s3_client=Mock(),
            config=ProviderConfig(
                key="test",
                provider_name="Test",
                endpoint_url="https://test.com",
                aws_access_key_id="key",
                aws_secret_access_key="secret",
                region_name="us-east-1",
                bucket_name="bucket",
            ),
        )

    def test_case_1_sends_truncated_body(self, executor):
        """Case 1 should send body smaller than header claims (CL > body)."""
        chunk_data = b"x" * 1000
        data_gen, headers = executor.prepare_case_data("case_1", chunk_data)

        body = b"".join(data_gen)
        assert len(body) == 999  # Body truncated
        assert int(headers["Content-Length"]) == 1000  # Header claims full size

    def test_case_2_sends_extended_body(self, executor):
        """Case 2 should send body larger than header claims (CL < body)."""
        chunk_data = b"x" * 1000
        data_gen, headers = executor.prepare_case_data("case_2", chunk_data)

        body = b"".join(data_gen)
        assert len(body) == 1001  # Body extended
        assert int(headers["Content-Length"]) == 1000  # Header claims normal size

    def test_case_5_sends_larger_than_signed(self, executor):
        """Case 5 should send matching header/body, but larger than signed value."""
        chunk_data = b"x" * 1000
        data_gen, headers = executor.prepare_case_data("case_5", chunk_data)

        body = b"".join(data_gen)
        # Both body and header should match, but be larger than the signed value (1000)
        assert len(body) == 1001
        assert int(headers["Content-Length"]) == 1001

    def test_case_6_sends_smaller_than_signed(self, executor):
        """Case 6 should send matching header/body, but smaller than signed value."""
        chunk_data = b"x" * 1000
        data_gen, headers = executor.prepare_case_data("case_6", chunk_data)

        body = b"".join(data_gen)
        # Both body and header should match, but be smaller than the signed value (1000)
        assert len(body) == 999
        assert int(headers["Content-Length"]) == 999

    def test_case_7_sends_exact_data(self, executor):
        """Case 7 (control) should send exact data matching header and signed value."""
        chunk_data = b"x" * 1000
        data_gen, headers = executor.prepare_case_data("case_7", chunk_data)

        body = b"".join(data_gen)
        assert len(body) == 1000
        assert int(headers["Content-Length"]) == 1000

    # Single-part upload case tests (case_9-12)
    def test_case_9_single_part_truncated_body(self, executor):
        """Case 9 should send body smaller than header claims (single-part)."""
        chunk_data = b"x" * 1000
        data_gen, headers = executor.prepare_case_data("case_9", chunk_data)

        body = b"".join(data_gen)
        assert len(body) == 999  # Body truncated
        assert int(headers["Content-Length"]) == 1000  # Header claims full size

    def test_case_10_single_part_extended_body(self, executor):
        """Case 10 should send body larger than header claims (single-part)."""
        chunk_data = b"x" * 1000
        data_gen, headers = executor.prepare_case_data("case_10", chunk_data)

        body = b"".join(data_gen)
        assert len(body) == 1001  # Body extended
        assert int(headers["Content-Length"]) == 1000  # Header claims normal size

    def test_case_11_single_part_larger_than_signed(self, executor):
        """Case 11 should send matching header/body, but larger than signed value (single-part)."""
        chunk_data = b"x" * 1000
        data_gen, headers = executor.prepare_case_data("case_11", chunk_data)

        body = b"".join(data_gen)
        assert len(body) == 1001
        assert int(headers["Content-Length"]) == 1001

    def test_case_12_single_part_control(self, executor):
        """Case 12 (single-part control) should send exact data matching header and signed value."""
        chunk_data = b"x" * 1000
        data_gen, headers = executor.prepare_case_data("case_12", chunk_data)

        body = b"".join(data_gen)
        assert len(body) == 1000
        assert int(headers["Content-Length"]) == 1000
