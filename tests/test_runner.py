"""Tests for runner.py module.

Tests the main test orchestrator that coordinates test execution.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import os

from src.runner import (
    EnforcementRunner,
    ProviderTestSession,
    RunResult,
)
from src.models import ProviderConfig, ResultStatus, ProviderResult, CaseResult
from src.test_cases import CASE_DEFINITIONS


class TestRunResult:
    """Tests for RunResult dataclass."""

    def test_create_run_result(self):
        """Should create a run result with provider results."""
        provider_result = ProviderResult(
            provider_key="test",
            provider_name="Test Provider",
            status=ResultStatus.PASS,
        )
        result = RunResult(
            providers={"test": provider_result},
            total_duration=10.5,
        )

        assert result.providers["test"] is provider_result
        assert result.total_duration == 10.5

    def test_all_passed_when_all_pass(self):
        """all_passed should be True when all providers pass."""
        result = RunResult(
            providers={
                "p1": ProviderResult("p1", "Provider 1", ResultStatus.PASS),
                "p2": ProviderResult("p2", "Provider 2", ResultStatus.PASS),
            },
            total_duration=1.0,
        )
        assert result.all_passed is True

    def test_all_passed_false_when_one_fails(self):
        """all_passed should be False when any provider fails."""
        result = RunResult(
            providers={
                "p1": ProviderResult("p1", "Provider 1", ResultStatus.PASS),
                "p2": ProviderResult("p2", "Provider 2", ResultStatus.FAIL),
            },
            total_duration=1.0,
        )
        assert result.all_passed is False

    def test_all_passed_false_when_one_errors(self):
        """all_passed should be False when any provider has an error."""
        result = RunResult(
            providers={
                "p1": ProviderResult("p1", "Provider 1", ResultStatus.PASS),
                "p2": ProviderResult("p2", "Provider 2", ResultStatus.ERROR),
            },
            total_duration=1.0,
        )
        assert result.all_passed is False


class TestProviderTestSession:
    """Tests for ProviderTestSession class."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        client = Mock()
        client.create_multipart_upload.return_value = {"UploadId": "upload-123"}
        client.generate_presigned_url.return_value = "https://example.com/presigned"
        client.list_parts.return_value = {"Parts": []}
        client.complete_multipart_upload.return_value = {"ETag": '"final"'}
        return client

    @pytest.fixture
    def mock_http_client(self):
        """Create a mock HTTP client."""
        client = Mock()
        response = Mock()
        response.status_code = 200
        response.headers = {"ETag": '"part-etag"'}
        response.raise_for_status = Mock()
        client.put.return_value = response
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

    def test_session_initialization(self, mock_s3_client, mock_http_client, provider_config):
        """Should initialize session with clients and config."""
        session = ProviderTestSession(
            s3_client=mock_s3_client,
            http_client=mock_http_client,
            config=provider_config,
        )

        assert session.s3_client is mock_s3_client
        assert session.http_client is mock_http_client
        assert session.config is provider_config

    def test_run_case_for_part(self, mock_s3_client, mock_http_client, provider_config):
        """Should run a test case for a specific part."""
        session = ProviderTestSession(
            s3_client=mock_s3_client,
            http_client=mock_http_client,
            config=provider_config,
        )

        chunk_data = b"x" * 1000
        result = session.run_case_for_part(
            case_id="case_7",
            upload_id="upload-123",
            part_number=1,
            chunk_data=chunk_data,
        )

        assert result.case_id == "case_7"
        assert result.passed is True

    def test_run_all_cases_for_part(self, mock_s3_client, mock_http_client, provider_config):
        """Should run all upload test cases (1, 2, 5, 6, 7) for a part.

        Note: case_3 (Body Truncated) and case_4 (Body Extended) were consolidated
        into case_1 and case_2 respectively, as they test the same enforcement.
        """
        # Configure mock to fail appropriately for failure cases
        def mock_put(url, content, headers):
            response = Mock()
            cl = int(headers.get("Content-Length", 0))
            # Fail if Content-Length doesn't match what was signed (1000)
            if cl != 1000:
                response.status_code = 403
                response.raise_for_status.side_effect = Exception("Signature mismatch")
            else:
                response.status_code = 200
                response.headers = {"ETag": '"etag"'}
                response.raise_for_status = Mock()
            return response

        mock_http_client.put.side_effect = mock_put

        session = ProviderTestSession(
            s3_client=mock_s3_client,
            http_client=mock_http_client,
            config=provider_config,
        )

        chunk_data = b"x" * 1000
        results = session.run_all_cases_for_part(
            upload_id="upload-123",
            part_number=1,
            chunk_data=chunk_data,
        )

        # Should return results for cases 1, 2, 5, 6, 7 (5 upload test cases)
        assert len(results) == 5
        case_ids = [r.case_id for r in results]
        expected_case_ids = ["case_1", "case_2", "case_5", "case_6", "case_7"]
        for case_id in expected_case_ids:
            assert case_id in case_ids

    def test_run_list_parts_test(self, mock_s3_client, mock_http_client, provider_config):
        """Should run the list parts verification test."""
        mock_s3_client.list_parts.return_value = {
            "Parts": [{"PartNumber": 1, "ETag": '"etag1"'}]
        }

        session = ProviderTestSession(
            s3_client=mock_s3_client,
            http_client=mock_http_client,
            config=provider_config,
        )

        expected_parts = [{"PartNumber": 1, "ETag": '"etag1"'}]
        result = session.run_list_parts_test(
            upload_id="upload-123",
            expected_parts=expected_parts,
        )

        assert result.case_id == "case_8"
        assert result.passed is True

    def test_run_all_single_part_cases(self, mock_s3_client, mock_http_client, provider_config):
        """Should run all single-part upload test cases (case_9 through case_12)."""
        # Configure mock to fail appropriately for failure cases
        def mock_put(url, content, headers):
            response = Mock()
            cl = int(headers.get("Content-Length", 0))
            # Fail if Content-Length doesn't match what was signed (1024)
            if cl != 1024:
                response.status_code = 403
                response.raise_for_status.side_effect = Exception("Signature mismatch")
            else:
                response.status_code = 200
                response.headers = {"ETag": '"etag"'}
                response.raise_for_status = Mock()
            return response

        mock_http_client.put.side_effect = mock_put

        session = ProviderTestSession(
            s3_client=mock_s3_client,
            http_client=mock_http_client,
            config=provider_config,
        )

        test_data = b"x" * 1024
        results = session.run_all_single_part_cases(test_data)

        # Should return results for cases 9, 10, 11, 12 (4 single-part test cases)
        assert len(results) == 4
        case_ids = [r.case_id for r in results]
        expected_case_ids = ["case_9", "case_10", "case_11", "case_12"]
        for case_id in expected_case_ids:
            assert case_id in case_ids

    def test_cleanup_single_part_objects(self, mock_s3_client, mock_http_client, provider_config):
        """Should clean up single-part test objects."""
        session = ProviderTestSession(
            s3_client=mock_s3_client,
            http_client=mock_http_client,
            config=provider_config,
        )

        session.cleanup_single_part_objects()

        mock_s3_client.delete_object.assert_called_once()


class TestEnforcementRunner:
    """Tests for the EnforcementRunner class."""

    @pytest.fixture
    def provider_configs(self):
        """Create test provider configurations."""
        return {
            "provider1": ProviderConfig(
                key="provider1",
                provider_name="Provider 1",
                endpoint_url="https://p1.example.com",
                aws_access_key_id="key1",
                aws_secret_access_key="secret1",
                region_name="us-east-1",
                bucket_name="bucket1",
            ),
            "provider2": ProviderConfig(
                key="provider2",
                provider_name="Provider 2",
                endpoint_url="https://p2.example.com",
                aws_access_key_id="key2",
                aws_secret_access_key="secret2",
                region_name="us-west-2",
                bucket_name="bucket2",
            ),
        }

    def test_runner_initialization(self, provider_configs):
        """Should store provider configurations."""
        runner = EnforcementRunner(provider_configs)
        assert runner.providers == provider_configs

    def test_runner_with_reporter(self, provider_configs):
        """Should accept optional reporter."""
        reporter = Mock()
        runner = EnforcementRunner(provider_configs, reporter=reporter)
        assert runner.reporter is reporter

    @patch("src.runner.build_s3_client")
    @patch("src.runner.httpx.Client")
    @patch("src.runner.create_test_file")
    def test_run_executes_all_providers(
        self,
        mock_create_file,
        mock_http_client_class,
        mock_build_s3,
        provider_configs,
    ):
        """Should run tests for all configured providers."""
        # Setup mocks
        mock_create_file.return_value = "/tmp/test.bin"
        mock_s3 = Mock()
        mock_s3.create_multipart_upload.return_value = {"UploadId": "id"}
        mock_s3.generate_presigned_url.return_value = "https://presigned"
        mock_s3.list_parts.return_value = {"Parts": []}
        mock_s3.complete_multipart_upload.return_value = {"ETag": '"final"'}
        mock_build_s3.return_value = mock_s3

        mock_http = Mock()
        response = Mock()
        response.status_code = 200
        response.headers = {"ETag": '"etag"'}
        response.raise_for_status = Mock()
        mock_http.put.return_value = response
        mock_http_client_class.return_value = mock_http

        runner = EnforcementRunner(provider_configs)

        with patch("os.path.exists", return_value=True):
            with patch("os.remove"):
                with patch.object(runner, "_run_provider_tests") as mock_run:
                    mock_run.return_value = ProviderResult(
                        provider_key="test",
                        provider_name="Test",
                        status=ResultStatus.PASS,
                    )
                    result = runner.run()

        # Should have results for both providers
        assert len(result.providers) == 2
        assert "provider1" in result.providers
        assert "provider2" in result.providers

    def test_run_reports_provider_start(self, provider_configs):
        """Should call reporter on_provider_start for each provider."""
        reporter = Mock()
        runner = EnforcementRunner(provider_configs, reporter=reporter)

        with patch.object(runner, "_run_provider_tests") as mock_run:
            mock_run.return_value = ProviderResult(
                provider_key="test",
                provider_name="Test",
                status=ResultStatus.PASS,
            )
            runner.run()

        # Should have called on_provider_start for both providers
        assert reporter.on_provider_start.call_count == 2

    def test_run_reports_provider_complete(self, provider_configs):
        """Should call reporter on_provider_complete for each provider."""
        reporter = Mock()
        runner = EnforcementRunner(provider_configs, reporter=reporter)

        with patch.object(runner, "_run_provider_tests") as mock_run:
            mock_run.return_value = ProviderResult(
                provider_key="test",
                provider_name="Test",
                status=ResultStatus.PASS,
            )
            runner.run()

        # Should have called on_provider_complete for both providers
        assert reporter.on_provider_complete.call_count == 2

    def test_run_reports_run_complete(self, provider_configs):
        """Should call reporter on_run_complete at the end."""
        reporter = Mock()
        runner = EnforcementRunner(provider_configs, reporter=reporter)

        with patch.object(runner, "_run_provider_tests") as mock_run:
            mock_run.return_value = ProviderResult(
                provider_key="test",
                provider_name="Test",
                status=ResultStatus.PASS,
            )
            runner.run()

        reporter.on_run_complete.assert_called_once()


class TestProviderTestExecution:
    """Tests for full provider test execution flow."""

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

    @patch("src.runner.build_s3_client")
    @patch("src.runner.httpx.Client")
    @patch("src.runner.create_test_file")
    def test_provider_error_results_in_error_status(
        self,
        mock_create_file,
        mock_http_client_class,
        mock_build_s3,
        provider_config,
    ):
        """Provider that throws error should get ERROR status."""
        mock_create_file.return_value = "/tmp/test.bin"
        mock_build_s3.side_effect = Exception("Connection failed")

        runner = EnforcementRunner({"test": provider_config})

        with patch("os.path.exists", return_value=True):
            with patch("os.remove"):
                result = runner.run()

        assert result.providers["test"].status == ResultStatus.ERROR
        assert "Connection failed" in result.providers["test"].error_message

    @patch("src.runner.build_s3_client")
    @patch("src.runner.httpx.Client")
    @patch("src.runner.create_test_file")
    def test_all_cases_pass_results_in_pass_status(
        self,
        mock_create_file,
        mock_http_client_class,
        mock_build_s3,
        provider_config,
    ):
        """Provider with all passing cases should get PASS status."""
        mock_create_file.return_value = "/tmp/test.bin"

        # Setup S3 client mock
        mock_s3 = Mock()
        mock_s3.create_multipart_upload.return_value = {"UploadId": "id"}
        mock_s3.generate_presigned_url.return_value = "https://presigned"
        mock_s3.list_parts.return_value = {"Parts": [{"PartNumber": 1, "ETag": '"etag"'}]}
        mock_s3.complete_multipart_upload.return_value = {"ETag": '"final"'}
        mock_build_s3.return_value = mock_s3

        # Setup HTTP client mock - proper behavior for each case
        mock_http = Mock()

        def mock_put(url, content, headers):
            response = Mock()
            cl = int(headers.get("Content-Length", 0))
            # Only case 7 should succeed (correct Content-Length)
            # All others should fail
            body = b"".join(content) if hasattr(content, "__iter__") else content
            body_len = len(body) if body else 0

            # Simulate proper enforcement
            if cl == body_len == 5242880:  # 5 MiB exact match
                response.status_code = 200
                response.headers = {"ETag": '"etag"'}
                response.raise_for_status = Mock()
            else:
                response.status_code = 403
                response.raise_for_status.side_effect = Exception("Mismatch")
            return response

        mock_http.put.side_effect = mock_put
        mock_http.close = Mock()
        mock_http_client_class.return_value = mock_http

        runner = EnforcementRunner({"test": provider_config})

        with patch("os.path.exists", return_value=True):
            with patch("os.remove"):
                # Mock the file iteration to return small chunks
                with patch.object(
                    runner,
                    "_run_provider_tests",
                    return_value=ProviderResult(
                        provider_key="test",
                        provider_name="Test Provider",
                        status=ResultStatus.PASS,
                    ),
                ):
                    result = runner.run()

        assert result.providers["test"].status == ResultStatus.PASS


class TestRunnerCleanup:
    """Tests for cleanup behavior."""

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

    @patch("src.runner.build_s3_client")
    @patch("src.runner.httpx.Client")
    @patch("src.runner.create_test_file")
    def test_cleans_up_test_file_on_success(
        self,
        mock_create_file,
        mock_http_client_class,
        mock_build_s3,
        provider_config,
    ):
        """Should clean up test file after successful run."""
        mock_create_file.return_value = "/tmp/test.bin"
        mock_build_s3.return_value = Mock()
        mock_http_client_class.return_value = Mock()

        runner = EnforcementRunner({"test": provider_config})

        with patch("os.path.exists", return_value=True) as mock_exists:
            with patch("os.remove") as mock_remove:
                with patch.object(
                    runner,
                    "_run_provider_tests",
                    return_value=ProviderResult(
                        provider_key="test",
                        provider_name="Test",
                        status=ResultStatus.PASS,
                    ),
                ):
                    runner.run()

        mock_remove.assert_called_with("/tmp/test.bin")

    @patch("src.runner.build_s3_client")
    @patch("src.runner.httpx.Client")
    @patch("src.runner.create_test_file")
    def test_cleans_up_test_file_on_error(
        self,
        mock_create_file,
        mock_http_client_class,
        mock_build_s3,
        provider_config,
    ):
        """Should clean up test file even when provider errors."""
        mock_create_file.return_value = "/tmp/test.bin"
        mock_build_s3.side_effect = Exception("Failed")
        mock_http_client_class.return_value = Mock()

        runner = EnforcementRunner({"test": provider_config})

        with patch("os.path.exists", return_value=True):
            with patch("os.remove") as mock_remove:
                runner.run()

        mock_remove.assert_called_with("/tmp/test.bin")
