"""S3 client factory for the enforcement tester.

Creates boto3 S3 clients configured for each provider, with the correct
endpoint, credentials, region, and addressing style.

The signature version is set to 's3v4' to ensure Content-Length can be
signed into presigned URLs.
"""

import boto3
from botocore.client import Config

from src.models import ProviderConfig


def build_s3_client(config: ProviderConfig):
    """Build a boto3 S3 client for the given provider configuration.

    Args:
        config: Provider configuration containing endpoint, credentials,
               region, and addressing style.

    Returns:
        A boto3 S3 client configured for the provider.

    Note:
        The signature version is set to 's3v4' which is required for
        signing Content-Length into presigned URLs. This is the key
        to the enforcement mechanism.
    """
    boto_config = Config(
        signature_version="s3v4",
        s3={"addressing_style": config.addressing_style},
    )

    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
        region_name=config.region_name,
        config=boto_config,
    )
