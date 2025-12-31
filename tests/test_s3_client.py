"""Tests for S3 client factory module."""

from unittest.mock import MagicMock, patch

import pytest

from src.models import ProviderConfig
from src.s3_client import build_s3_client


class TestBuildS3Client:
    """Tests for build_s3_client function."""

    @pytest.fixture
    def provider_config(self) -> ProviderConfig:
        """Create a sample provider config for testing."""
        return ProviderConfig(
            key="b2",
            provider_name="Backblaze B2",
            endpoint_url="https://s3.us-west-000.backblazeb2.com",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
            region_name="us-west-000",
            bucket_name="test-bucket",
            addressing_style="virtual",
        )

    @patch("src.s3_client.boto3.client")
    def test_correct_endpoint_and_credentials(
        self, mock_boto_client: MagicMock, provider_config: ProviderConfig
    ):
        """Verify endpoint, credentials, and region are passed to boto3."""
        build_s3_client(provider_config)

        mock_boto_client.assert_called_once()
        call_kwargs = mock_boto_client.call_args.kwargs

        assert call_kwargs["endpoint_url"] == "https://s3.us-west-000.backblazeb2.com"
        assert call_kwargs["aws_access_key_id"] == "test-access-key"
        assert call_kwargs["aws_secret_access_key"] == "test-secret-key"
        assert call_kwargs["region_name"] == "us-west-000"

    @patch("src.s3_client.boto3.client")
    def test_virtual_addressing_style(
        self, mock_boto_client: MagicMock, provider_config: ProviderConfig
    ):
        """Verify virtual addressing style is configured correctly."""
        build_s3_client(provider_config)

        call_kwargs = mock_boto_client.call_args.kwargs
        config = call_kwargs["config"]

        assert config.s3["addressing_style"] == "virtual"

    @patch("src.s3_client.boto3.client")
    def test_path_addressing_style(self, mock_boto_client: MagicMock):
        """Verify path addressing style is configured correctly."""
        config = ProviderConfig(
            key="r2",
            provider_name="Cloudflare R2",
            endpoint_url="https://account.r2.cloudflarestorage.com",
            aws_access_key_id="r2-key",
            aws_secret_access_key="r2-secret",
            region_name="auto",
            bucket_name="test-bucket",
            addressing_style="path",
        )

        build_s3_client(config)

        call_kwargs = mock_boto_client.call_args.kwargs
        boto_config = call_kwargs["config"]

        assert boto_config.s3["addressing_style"] == "path"

    @patch("src.s3_client.boto3.client")
    def test_signature_version_is_s3v4(
        self, mock_boto_client: MagicMock, provider_config: ProviderConfig
    ):
        """Verify signature version is set to s3v4 for presigned URLs."""
        build_s3_client(provider_config)

        call_kwargs = mock_boto_client.call_args.kwargs
        config = call_kwargs["config"]

        assert config.signature_version == "s3v4"

    @patch("src.s3_client.boto3.client")
    def test_returns_s3_client(
        self, mock_boto_client: MagicMock, provider_config: ProviderConfig
    ):
        """Verify function returns the boto3 client."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        result = build_s3_client(provider_config)

        assert result is mock_client

    @patch("src.s3_client.boto3.client")
    def test_first_argument_is_s3(
        self, mock_boto_client: MagicMock, provider_config: ProviderConfig
    ):
        """Verify first argument to boto3.client is 's3'."""
        build_s3_client(provider_config)

        call_args = mock_boto_client.call_args
        assert call_args.args[0] == "s3"
