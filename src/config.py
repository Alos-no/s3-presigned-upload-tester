"""Configuration loading for S3 enforcement tester.

Supports two configuration sources:
1. Environment variables (for CI/CD) - takes priority
2. config.json file (for local development)

Environment Variable Format:
    PROVIDER_{KEY}=Name|Endpoint|Region|Style
    {KEY}_ACCESS_KEY=xxx
    {KEY}_SECRET_KEY=xxx
    {KEY}_BUCKET=xxx

Example:
    PROVIDER_B2=Backblaze B2|https://s3.us-west-000.backblazeb2.com|us-west-000|virtual
    B2_ACCESS_KEY=your-access-key
    B2_SECRET_KEY=your-secret-key
    B2_BUCKET=your-bucket-name
"""

import json
import os
from pathlib import Path
from typing import Optional

from src.models import ProviderConfig


class ConfigError(Exception):
    """Raised when configuration loading fails."""

    pass


# Required fields for a provider configuration
REQUIRED_FIELDS = [
    "provider_name",
    "endpoint_url",
    "aws_access_key_id",
    "aws_secret_access_key",
    "region_name",
    "bucket_name",
]


def load_from_json(config_path: str) -> dict[str, ProviderConfig]:
    """Load provider configurations from a JSON file.

    Args:
        config_path: Path to the config.json file.

    Returns:
        Dictionary mapping provider keys to ProviderConfig objects.
        Only enabled providers are included.

    Raises:
        ConfigError: If file doesn't exist, contains invalid JSON,
                    or is missing required fields.
    """
    path = Path(config_path)

    if not path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config file: {e}") from e

    providers: dict[str, ProviderConfig] = {}

    for key, config in data.items():
        # Skip disabled providers
        if not config.get("enabled", True):
            continue

        # Validate required fields
        for field in REQUIRED_FIELDS:
            if field not in config:
                raise ConfigError(
                    f"Missing required field '{field}' for provider '{key}'"
                )

        providers[key] = ProviderConfig(
            key=key,
            provider_name=config["provider_name"],
            endpoint_url=config["endpoint_url"],
            aws_access_key_id=config["aws_access_key_id"],
            aws_secret_access_key=config["aws_secret_access_key"],
            region_name=config["region_name"],
            bucket_name=config["bucket_name"],
            addressing_style=config.get("addressing_style", "path"),
            enabled=True,
        )

    return providers


def load_from_env() -> dict[str, ProviderConfig]:
    """Load provider configurations from environment variables.

    Discovers providers by looking for PROVIDER_* environment variables.
    For each provider, expects corresponding credential variables.

    Returns:
        Dictionary mapping provider keys to ProviderConfig objects.

    Raises:
        ConfigError: If environment variables are malformed or
                    required credential variables are missing.
    """
    providers: dict[str, ProviderConfig] = {}

    # Find all PROVIDER_* environment variables
    for env_key, env_value in os.environ.items():
        if not env_key.startswith("PROVIDER_"):
            continue

        # Extract provider key (e.g., "PROVIDER_B2" -> "B2")
        provider_key = env_key.replace("PROVIDER_", "")

        # Parse pipe-delimited value: Name|Endpoint|Region|Style
        parts = env_value.split("|")
        if len(parts) != 4:
            raise ConfigError(
                f"Invalid format for {env_key}. Expected: Name|Endpoint|Region|Style"
            )

        name, endpoint, region, style = parts

        # Look up credential environment variables
        access_key_var = f"{provider_key}_ACCESS_KEY"
        secret_key_var = f"{provider_key}_SECRET_KEY"
        bucket_var = f"{provider_key}_BUCKET"

        access_key = os.environ.get(access_key_var)
        if not access_key:
            raise ConfigError(f"Missing environment variable: {access_key_var}")

        secret_key = os.environ.get(secret_key_var)
        if not secret_key:
            raise ConfigError(f"Missing environment variable: {secret_key_var}")

        bucket = os.environ.get(bucket_var)
        if not bucket:
            raise ConfigError(f"Missing environment variable: {bucket_var}")

        providers[provider_key] = ProviderConfig(
            key=provider_key,
            provider_name=name,
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            bucket_name=bucket,
            addressing_style=style,
            enabled=True,
        )

    return providers


def has_env_providers() -> bool:
    """Check if any PROVIDER_* environment variables exist."""
    return any(key.startswith("PROVIDER_") for key in os.environ)


def load_providers(
    config_path: str = "config.json",
) -> dict[str, ProviderConfig]:
    """Load provider configurations with environment priority.

    Priority order:
    1. Environment variables (if any PROVIDER_* vars exist)
    2. config.json file

    Args:
        config_path: Path to config.json (used as fallback).

    Returns:
        Dictionary mapping provider keys to ProviderConfig objects.

    Raises:
        ConfigError: If no providers are configured or all are disabled.
    """
    providers: dict[str, ProviderConfig] = {}

    if has_env_providers():
        providers = load_from_env()
    elif Path(config_path).exists():
        providers = load_from_json(config_path)

    if not providers:
        raise ConfigError(
            "No providers configured. Set PROVIDER_* environment variables "
            "or create a config.json file with at least one enabled provider."
        )

    return providers
