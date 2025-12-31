"""Multipart upload lifecycle management.

Handles the complete lifecycle of S3 multipart uploads:
- Initiate upload
- Track uploaded parts
- Complete or abort upload
- Cleanup resources
"""

import os
import tempfile
from typing import Any, Generator, Optional

from src.models import ProviderConfig

# Test object key used for all uploads
TEST_OBJECT_KEY = "e2e-multipart-test.bin"

# Default file size: 12 MiB (requires multiple 5 MiB parts)
DEFAULT_FILE_SIZE = 12 * 1024 * 1024

# Default chunk size: 5 MiB (S3 minimum part size)
DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024


def create_test_file(size: int = DEFAULT_FILE_SIZE) -> str:
    """Create a temporary file with random data for testing.

    Args:
        size: Size of the file in bytes.

    Returns:
        Path to the created temporary file.
    """
    fd, file_path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, "wb") as f:
            # Write in 1 MiB chunks for efficiency
            chunk_size = 1024 * 1024
            remaining = size
            while remaining > 0:
                write_size = min(chunk_size, remaining)
                f.write(os.urandom(write_size))
                remaining -= write_size
    except Exception:
        os.close(fd)
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    return file_path


class MultipartUpload:
    """Manages the lifecycle of a multipart upload.

    This class handles:
    - Initiating a multipart upload
    - Tracking uploaded parts and their ETags
    - Completing or aborting the upload
    - Cleaning up remote resources

    Can be used as a context manager for automatic cleanup on errors.
    """

    def __init__(self, s3_client: Any, config: ProviderConfig):
        """Initialize the multipart upload manager.

        Args:
            s3_client: boto3 S3 client
            config: Provider configuration
        """
        self.s3_client = s3_client
        self.config = config
        self.upload_id: Optional[str] = None
        self.uploaded_parts: list[dict] = []

    def initiate(self) -> str:
        """Initiate a new multipart upload.

        Returns:
            The upload ID for the new multipart upload.

        Raises:
            Exception: If the API call fails.
        """
        response = self.s3_client.create_multipart_upload(
            Bucket=self.config.bucket_name,
            Key=TEST_OBJECT_KEY,
        )
        self.upload_id = response["UploadId"]
        return self.upload_id

    def complete(self) -> dict:
        """Complete the multipart upload.

        Returns:
            The API response containing the final ETag.

        Raises:
            RuntimeError: If upload was not initiated.
            Exception: If the API call fails.
        """
        if self.upload_id is None:
            raise RuntimeError("Upload not initiated")

        return self.s3_client.complete_multipart_upload(
            Bucket=self.config.bucket_name,
            Key=TEST_OBJECT_KEY,
            UploadId=self.upload_id,
            MultipartUpload={"Parts": self.uploaded_parts},
        )

    def abort(self) -> None:
        """Abort the multipart upload.

        Cleans up any uploaded parts on the provider's side.
        Safe to call even if upload was not initiated or already aborted.
        """
        if self.upload_id is None:
            return

        try:
            self.s3_client.abort_multipart_upload(
                Bucket=self.config.bucket_name,
                Key=TEST_OBJECT_KEY,
                UploadId=self.upload_id,
            )
        except Exception:
            # Abort errors are non-fatal - upload may already be aborted
            pass

    def cleanup_remote(self) -> None:
        """Delete the test object from S3.

        Safe to call even if object doesn't exist.
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.config.bucket_name,
                Key=TEST_OBJECT_KEY,
            )
        except Exception:
            # Delete errors are non-fatal
            pass

    def add_part(self, part_number: int, etag: str) -> None:
        """Record a successfully uploaded part.

        Args:
            part_number: The 1-indexed part number.
            etag: The ETag returned by the provider.
        """
        self.uploaded_parts.append({
            "PartNumber": part_number,
            "ETag": etag,
        })

    def get_uploaded_parts(self) -> list[dict]:
        """Get a copy of the uploaded parts list.

        Returns:
            Copy of the list of uploaded parts.
        """
        return list(self.uploaded_parts)

    def iterate_parts(
        self,
        file_path: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> Generator[tuple[int, bytes], None, None]:
        """Iterate over file parts.

        Args:
            file_path: Path to the file to read.
            chunk_size: Size of each chunk in bytes.

        Yields:
            Tuples of (part_number, chunk_data).
        """
        part_number = 1
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield part_number, chunk
                part_number += 1

    def __enter__(self) -> "MultipartUpload":
        """Enter context manager - initiates upload."""
        self.initiate()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit context manager - aborts on exception."""
        if exc_type is not None:
            self.abort()
        return False  # Don't suppress exceptions
