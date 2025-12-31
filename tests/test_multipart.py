"""Tests for multipart.py module.

Tests the multipart upload lifecycle: initiate, upload parts, complete, abort.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from src.multipart import (
    MultipartUpload,
    create_test_file,
    TEST_OBJECT_KEY,
    DEFAULT_FILE_SIZE,
    DEFAULT_CHUNK_SIZE,
)
from src.models import ProviderConfig


class TestConstants:
    """Tests for module constants."""

    def test_object_key_defined(self):
        """Test object key should be defined."""
        assert TEST_OBJECT_KEY == "e2e-multipart-test.bin"

    def test_default_file_size(self):
        """Default file size should be 12 MiB."""
        assert DEFAULT_FILE_SIZE == 12 * 1024 * 1024

    def test_default_chunk_size(self):
        """Default chunk size should be 5 MiB (S3 minimum)."""
        assert DEFAULT_CHUNK_SIZE == 5 * 1024 * 1024


class TestCreateTestFile:
    """Tests for create_test_file function."""

    def test_creates_file_with_correct_size(self):
        """Should create a file with the specified size."""
        size = 1024 * 10  # 10 KB for testing
        file_path = create_test_file(size)
        try:
            assert os.path.exists(file_path)
            assert os.path.getsize(file_path) == size
        finally:
            os.remove(file_path)

    def test_creates_file_with_random_data(self):
        """File should contain random data (not all zeros)."""
        size = 1024
        file_path = create_test_file(size)
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            # Random data should have some variation
            assert len(set(data)) > 10  # At least 10 different byte values
        finally:
            os.remove(file_path)

    def test_file_is_in_temp_directory(self):
        """File should be created in system temp directory."""
        file_path = create_test_file(1024)
        try:
            assert tempfile.gettempdir() in file_path
        finally:
            os.remove(file_path)


class TestMultipartUploadInit:
    """Tests for MultipartUpload initialization."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        client = Mock()
        client.create_multipart_upload.return_value = {"UploadId": "test-upload-id"}
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

    def test_initialization(self, mock_s3_client, provider_config):
        """Should store S3 client and config."""
        upload = MultipartUpload(mock_s3_client, provider_config)
        assert upload.s3_client is mock_s3_client
        assert upload.config is provider_config
        assert upload.upload_id is None
        assert upload.uploaded_parts == []

    def test_initiate_upload(self, mock_s3_client, provider_config):
        """Should initiate multipart upload and store upload ID."""
        upload = MultipartUpload(mock_s3_client, provider_config)
        upload_id = upload.initiate()

        assert upload_id == "test-upload-id"
        assert upload.upload_id == "test-upload-id"
        mock_s3_client.create_multipart_upload.assert_called_once_with(
            Bucket="test-bucket",
            Key=TEST_OBJECT_KEY,
        )

    def test_initiate_raises_on_failure(self, mock_s3_client, provider_config):
        """Should raise exception if initiate fails."""
        mock_s3_client.create_multipart_upload.side_effect = Exception("API error")
        upload = MultipartUpload(mock_s3_client, provider_config)

        with pytest.raises(Exception, match="API error"):
            upload.initiate()


class TestMultipartUploadComplete:
    """Tests for completing multipart uploads."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        client = Mock()
        client.create_multipart_upload.return_value = {"UploadId": "test-upload-id"}
        client.complete_multipart_upload.return_value = {"ETag": '"final-etag"'}
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

    def test_complete_upload(self, mock_s3_client, provider_config):
        """Should complete multipart upload with uploaded parts."""
        upload = MultipartUpload(mock_s3_client, provider_config)
        upload.initiate()
        upload.uploaded_parts = [
            {"PartNumber": 1, "ETag": '"etag1"'},
            {"PartNumber": 2, "ETag": '"etag2"'},
        ]

        result = upload.complete()

        assert result == {"ETag": '"final-etag"'}
        mock_s3_client.complete_multipart_upload.assert_called_once_with(
            Bucket="test-bucket",
            Key=TEST_OBJECT_KEY,
            UploadId="test-upload-id",
            MultipartUpload={"Parts": upload.uploaded_parts},
        )

    def test_complete_without_initiate_raises(self, mock_s3_client, provider_config):
        """Should raise if complete called without initiate."""
        upload = MultipartUpload(mock_s3_client, provider_config)

        with pytest.raises(RuntimeError, match="not initiated"):
            upload.complete()


class TestMultipartUploadAbort:
    """Tests for aborting multipart uploads."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        client = Mock()
        client.create_multipart_upload.return_value = {"UploadId": "test-upload-id"}
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

    def test_abort_upload(self, mock_s3_client, provider_config):
        """Should abort multipart upload."""
        upload = MultipartUpload(mock_s3_client, provider_config)
        upload.initiate()

        upload.abort()

        mock_s3_client.abort_multipart_upload.assert_called_once_with(
            Bucket="test-bucket",
            Key=TEST_OBJECT_KEY,
            UploadId="test-upload-id",
        )

    def test_abort_without_initiate_is_noop(self, mock_s3_client, provider_config):
        """Should not call API if upload not initiated."""
        upload = MultipartUpload(mock_s3_client, provider_config)

        upload.abort()  # Should not raise

        mock_s3_client.abort_multipart_upload.assert_not_called()

    def test_abort_handles_api_error_gracefully(self, mock_s3_client, provider_config):
        """Should handle abort API errors without raising."""
        mock_s3_client.abort_multipart_upload.side_effect = Exception("API error")
        upload = MultipartUpload(mock_s3_client, provider_config)
        upload.initiate()

        # Should not raise
        upload.abort()


class TestMultipartUploadCleanup:
    """Tests for cleanup after upload."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        return Mock()

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

    def test_cleanup_deletes_remote_object(self, mock_s3_client, provider_config):
        """Should delete the test object from S3."""
        upload = MultipartUpload(mock_s3_client, provider_config)

        upload.cleanup_remote()

        mock_s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key=TEST_OBJECT_KEY,
        )

    def test_cleanup_handles_delete_error(self, mock_s3_client, provider_config):
        """Should handle delete errors gracefully."""
        mock_s3_client.delete_object.side_effect = Exception("Delete failed")
        upload = MultipartUpload(mock_s3_client, provider_config)

        # Should not raise
        upload.cleanup_remote()


class TestMultipartUploadAddPart:
    """Tests for adding completed parts."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        client = Mock()
        client.create_multipart_upload.return_value = {"UploadId": "test-upload-id"}
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

    def test_add_part(self, mock_s3_client, provider_config):
        """Should add a completed part to the list."""
        upload = MultipartUpload(mock_s3_client, provider_config)
        upload.initiate()

        upload.add_part(1, '"etag1"')
        upload.add_part(2, '"etag2"')

        assert len(upload.uploaded_parts) == 2
        assert upload.uploaded_parts[0] == {"PartNumber": 1, "ETag": '"etag1"'}
        assert upload.uploaded_parts[1] == {"PartNumber": 2, "ETag": '"etag2"'}

    def test_get_uploaded_parts(self, mock_s3_client, provider_config):
        """Should return copy of uploaded parts list."""
        upload = MultipartUpload(mock_s3_client, provider_config)
        upload.initiate()
        upload.add_part(1, '"etag1"')

        parts = upload.get_uploaded_parts()

        assert parts == [{"PartNumber": 1, "ETag": '"etag1"'}]
        # Modifying returned list should not affect internal state
        parts.append({"PartNumber": 99, "ETag": '"fake"'})
        assert len(upload.uploaded_parts) == 1


class TestMultipartUploadContextManager:
    """Tests for context manager protocol."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        client = Mock()
        client.create_multipart_upload.return_value = {"UploadId": "test-upload-id"}
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

    def test_context_manager_initiates_on_enter(self, mock_s3_client, provider_config):
        """Should initiate upload on context entry."""
        with MultipartUpload(mock_s3_client, provider_config) as upload:
            assert upload.upload_id == "test-upload-id"

    def test_context_manager_aborts_on_exception(self, mock_s3_client, provider_config):
        """Should abort upload if exception occurs."""
        try:
            with MultipartUpload(mock_s3_client, provider_config) as upload:
                raise ValueError("Test error")
        except ValueError:
            pass

        mock_s3_client.abort_multipart_upload.assert_called_once()

    def test_context_manager_does_not_abort_on_success(self, mock_s3_client, provider_config):
        """Should not abort if no exception occurs."""
        with MultipartUpload(mock_s3_client, provider_config) as upload:
            pass

        mock_s3_client.abort_multipart_upload.assert_not_called()


class TestMultipartUploadIterateParts:
    """Tests for iterating over file parts."""

    def test_iterate_parts_yields_chunks(self):
        """Should yield chunks from a file."""
        # Create a test file
        file_path = create_test_file(1024 * 10)  # 10 KB
        try:
            upload = MultipartUpload(Mock(), Mock())
            chunks = list(upload.iterate_parts(file_path, chunk_size=1024 * 3))

            # 10 KB / 3 KB = 4 chunks (3+3+3+1)
            assert len(chunks) == 4
            assert all(isinstance(c, tuple) for c in chunks)
            assert all(len(c) == 2 for c in chunks)  # (part_number, data)

            # Part numbers should be 1-indexed
            part_numbers = [c[0] for c in chunks]
            assert part_numbers == [1, 2, 3, 4]

            # Total data should equal file size
            total_size = sum(len(c[1]) for c in chunks)
            assert total_size == 1024 * 10
        finally:
            os.remove(file_path)

    def test_iterate_parts_with_exact_division(self):
        """Should handle files that divide evenly into chunks."""
        file_path = create_test_file(1024 * 6)  # 6 KB
        try:
            upload = MultipartUpload(Mock(), Mock())
            chunks = list(upload.iterate_parts(file_path, chunk_size=1024 * 2))

            # 6 KB / 2 KB = 3 chunks exactly
            assert len(chunks) == 3
            for i, (part_num, data) in enumerate(chunks, 1):
                assert part_num == i
                assert len(data) == 1024 * 2
        finally:
            os.remove(file_path)
