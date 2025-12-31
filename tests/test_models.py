"""Tests for data models."""

import pytest
from src.models import (
    CaseResult,
    ProviderConfig,
    ProviderResult,
    ResultStatus,
)


class TestResultStatus:
    """Tests for ResultStatus enum."""

    def test_status_values(self):
        """Verify all expected status values exist."""
        assert ResultStatus.PASS.value == "pass"
        assert ResultStatus.FAIL.value == "fail"
        assert ResultStatus.ERROR.value == "error"


class TestProviderConfig:
    """Tests for ProviderConfig dataclass."""

    def test_create_with_all_fields(self):
        """Create config with all fields specified."""
        config = ProviderConfig(
            key="b2",
            provider_name="Backblaze B2",
            endpoint_url="https://s3.us-west-000.backblazeb2.com",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="us-west-000",
            bucket_name="test-bucket",
            addressing_style="virtual",
            enabled=True,
        )
        assert config.key == "b2"
        assert config.provider_name == "Backblaze B2"
        assert config.addressing_style == "virtual"
        assert config.enabled is True

    def test_default_addressing_style(self):
        """Verify default addressing style is 'path'."""
        config = ProviderConfig(
            key="r2",
            provider_name="Cloudflare R2",
            endpoint_url="https://account.r2.cloudflarestorage.com",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="auto",
            bucket_name="test-bucket",
        )
        assert config.addressing_style == "path"

    def test_default_enabled(self):
        """Verify default enabled is True."""
        config = ProviderConfig(
            key="aws",
            provider_name="AWS S3",
            endpoint_url="https://s3.amazonaws.com",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="us-east-1",
            bucket_name="test-bucket",
        )
        assert config.enabled is True


class TestCaseResultModel:
    """Tests for CaseResult dataclass."""

    def test_create_pass_result(self):
        """Create a passing test result."""
        result = CaseResult(
            case_id="case_1_cl_gt_body",
            case_name="Content-Length > Body",
            status=ResultStatus.PASS,
            expected="reject",
            actual="rejected",
        )
        assert result.status == ResultStatus.PASS
        assert result.error_message is None

    def test_create_fail_result_with_error(self):
        """Create a failing test result with error message."""
        result = CaseResult(
            case_id="case_5_signed_lt_actual",
            case_name="Signed < Actual",
            status=ResultStatus.FAIL,
            expected="reject",
            actual="accepted",
            error_message="Provider incorrectly accepted oversized upload",
        )
        assert result.status == ResultStatus.FAIL
        assert result.error_message is not None


class TestProviderResult:
    """Tests for ProviderResult dataclass."""

    def test_create_with_defaults(self):
        """Create result with default values."""
        result = ProviderResult(
            provider_key="b2",
            provider_name="Backblaze B2",
            status=ResultStatus.PASS,
        )
        assert result.cases == {}
        assert result.duration_seconds == 0.0
        assert result.error_message is None

    def test_create_with_cases(self):
        """Create result with case details."""
        case_result = CaseResult(
            case_id="case_7_control",
            case_name="Control Group",
            status=ResultStatus.PASS,
            expected="accept",
            actual="accepted",
        )
        result = ProviderResult(
            provider_key="r2",
            provider_name="Cloudflare R2",
            status=ResultStatus.PASS,
            cases={"case_7_control": case_result},
            duration_seconds=45.2,
        )
        assert len(result.cases) == 1
        assert result.duration_seconds == 45.2
