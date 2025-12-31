"""Tests for configuration loading module."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import (
    ConfigError,
    load_from_env,
    load_from_json,
    load_providers,
)
from src.models import ProviderConfig


class TestLoadFromJson:
    """Tests for load_from_json function."""

    def test_valid_config_with_all_fields(self, tmp_path: Path):
        """Load a valid config file with all fields specified."""
        config_data = {
            "b2": {
                "provider_name": "Backblaze B2",
                "enabled": True,
                "endpoint_url": "https://s3.us-west-000.backblazeb2.com",
                "aws_access_key_id": "test-key",
                "aws_secret_access_key": "test-secret",
                "region_name": "us-west-000",
                "bucket_name": "test-bucket",
                "addressing_style": "virtual",
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        providers = load_from_json(str(config_file))

        assert "b2" in providers
        assert providers["b2"].provider_name == "Backblaze B2"
        assert providers["b2"].endpoint_url == "https://s3.us-west-000.backblazeb2.com"
        assert providers["b2"].addressing_style == "virtual"

    def test_missing_file_raises_error(self, tmp_path: Path):
        """Raise ConfigError when config file doesn't exist."""
        config_file = tmp_path / "nonexistent.json"

        with pytest.raises(ConfigError, match="Config file not found"):
            load_from_json(str(config_file))

    def test_malformed_json_raises_error(self, tmp_path: Path):
        """Raise ConfigError when config file contains invalid JSON."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{ invalid json }")

        with pytest.raises(ConfigError, match="Invalid JSON"):
            load_from_json(str(config_file))

    def test_empty_config_returns_empty_dict(self, tmp_path: Path):
        """Return empty dict when config file has no providers."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        providers = load_from_json(str(config_file))

        assert providers == {}

    def test_disabled_provider_excluded(self, tmp_path: Path):
        """Exclude providers with enabled=false."""
        config_data = {
            "enabled_provider": {
                "provider_name": "Enabled",
                "enabled": True,
                "endpoint_url": "https://enabled.example.com",
                "aws_access_key_id": "key",
                "aws_secret_access_key": "secret",
                "region_name": "us-east-1",
                "bucket_name": "bucket",
            },
            "disabled_provider": {
                "provider_name": "Disabled",
                "enabled": False,
                "endpoint_url": "https://disabled.example.com",
                "aws_access_key_id": "key",
                "aws_secret_access_key": "secret",
                "region_name": "us-east-1",
                "bucket_name": "bucket",
            },
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        providers = load_from_json(str(config_file))

        assert "enabled_provider" in providers
        assert "disabled_provider" not in providers

    def test_default_addressing_style(self, tmp_path: Path):
        """Use 'path' as default addressing_style when not specified."""
        config_data = {
            "r2": {
                "provider_name": "Cloudflare R2",
                "enabled": True,
                "endpoint_url": "https://account.r2.cloudflarestorage.com",
                "aws_access_key_id": "key",
                "aws_secret_access_key": "secret",
                "region_name": "auto",
                "bucket_name": "bucket",
                # No addressing_style specified
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        providers = load_from_json(str(config_file))

        assert providers["r2"].addressing_style == "path"

    def test_missing_required_field_raises_error(self, tmp_path: Path):
        """Raise ConfigError when required field is missing."""
        config_data = {
            "incomplete": {
                "provider_name": "Incomplete",
                "enabled": True,
                # Missing endpoint_url and other required fields
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        with pytest.raises(ConfigError, match="Missing required field"):
            load_from_json(str(config_file))


class TestLoadFromEnv:
    """Tests for load_from_env function."""

    def test_valid_env_vars_parsed_correctly(self):
        """Parse valid PROVIDER_* environment variables."""
        env_vars = {
            "PROVIDER_B2": "Backblaze B2|https://s3.us-west-000.backblazeb2.com|us-west-000|virtual",
            "B2_ACCESS_KEY": "test-key",
            "B2_SECRET_KEY": "test-secret",
            "B2_BUCKET": "test-bucket",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            providers = load_from_env()

        assert "B2" in providers
        assert providers["B2"].provider_name == "Backblaze B2"
        assert providers["B2"].endpoint_url == "https://s3.us-west-000.backblazeb2.com"
        assert providers["B2"].region_name == "us-west-000"
        assert providers["B2"].addressing_style == "virtual"

    def test_no_provider_vars_returns_empty_dict(self):
        """Return empty dict when no PROVIDER_* vars exist."""
        # Clear any existing PROVIDER_* vars
        env_vars = {k: v for k, v in os.environ.items() if not k.startswith("PROVIDER_")}

        with patch.dict(os.environ, env_vars, clear=True):
            providers = load_from_env()

        assert providers == {}

    def test_missing_credential_env_var_raises_error(self):
        """Raise ConfigError with clear message when credential var is missing."""
        env_vars = {
            "PROVIDER_B2": "Backblaze B2|https://s3.example.com|us-west-000|virtual",
            "B2_ACCESS_KEY": "test-key",
            # Missing B2_SECRET_KEY and B2_BUCKET
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ConfigError, match="Missing environment variable.*B2_SECRET_KEY"):
                load_from_env()

    def test_malformed_pipe_delimited_value_raises_error(self):
        """Raise ConfigError when PROVIDER_* value has wrong format."""
        env_vars = {
            "PROVIDER_B2": "Only two|parts",  # Should have 4 parts
            "B2_ACCESS_KEY": "key",
            "B2_SECRET_KEY": "secret",
            "B2_BUCKET": "bucket",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ConfigError, match="Invalid format.*PROVIDER_B2"):
                load_from_env()

    def test_multiple_providers_discovered(self):
        """Discover multiple providers from environment variables."""
        env_vars = {
            "PROVIDER_B2": "Backblaze B2|https://b2.example.com|us-west-000|virtual",
            "B2_ACCESS_KEY": "b2-key",
            "B2_SECRET_KEY": "b2-secret",
            "B2_BUCKET": "b2-bucket",
            "PROVIDER_R2": "Cloudflare R2|https://r2.example.com|auto|path",
            "R2_ACCESS_KEY": "r2-key",
            "R2_SECRET_KEY": "r2-secret",
            "R2_BUCKET": "r2-bucket",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            providers = load_from_env()

        assert len(providers) == 2
        assert "B2" in providers
        assert "R2" in providers


class TestLoadProviders:
    """Tests for load_providers function."""

    def test_env_vars_take_priority(self, tmp_path: Path):
        """Environment variables take priority over config.json."""
        # Create a config file
        config_data = {
            "b2": {
                "provider_name": "From JSON",
                "enabled": True,
                "endpoint_url": "https://json.example.com",
                "aws_access_key_id": "json-key",
                "aws_secret_access_key": "json-secret",
                "region_name": "us-east-1",
                "bucket_name": "json-bucket",
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        # Set environment variables
        env_vars = {
            "PROVIDER_B2": "From ENV|https://env.example.com|us-west-000|path",
            "B2_ACCESS_KEY": "env-key",
            "B2_SECRET_KEY": "env-secret",
            "B2_BUCKET": "env-bucket",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            providers = load_providers(config_path=str(config_file))

        # Should use env vars, not JSON
        assert providers["B2"].provider_name == "From ENV"
        assert providers["B2"].endpoint_url == "https://env.example.com"

    def test_falls_back_to_config_json(self, tmp_path: Path):
        """Fall back to config.json when no env vars exist."""
        config_data = {
            "aws": {
                "provider_name": "AWS S3",
                "enabled": True,
                "endpoint_url": "https://s3.amazonaws.com",
                "aws_access_key_id": "aws-key",
                "aws_secret_access_key": "aws-secret",
                "region_name": "us-east-1",
                "bucket_name": "aws-bucket",
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        # Clear PROVIDER_* env vars
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("PROVIDER_")}

        with patch.dict(os.environ, clean_env, clear=True):
            providers = load_providers(config_path=str(config_file))

        assert "aws" in providers
        assert providers["aws"].provider_name == "AWS S3"

    def test_raises_error_when_neither_exists(self, tmp_path: Path):
        """Raise ConfigError when no env vars and no config file."""
        nonexistent_path = tmp_path / "nonexistent.json"

        # Clear PROVIDER_* env vars
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("PROVIDER_")}

        with patch.dict(os.environ, clean_env, clear=True):
            with pytest.raises(ConfigError, match="No providers configured"):
                load_providers(config_path=str(nonexistent_path))

    def test_raises_error_when_all_disabled(self, tmp_path: Path):
        """Raise ConfigError when all providers are disabled."""
        config_data = {
            "aws": {
                "provider_name": "AWS S3",
                "enabled": False,
                "endpoint_url": "https://s3.amazonaws.com",
                "aws_access_key_id": "key",
                "aws_secret_access_key": "secret",
                "region_name": "us-east-1",
                "bucket_name": "bucket",
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        # Clear PROVIDER_* env vars
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("PROVIDER_")}

        with patch.dict(os.environ, clean_env, clear=True):
            with pytest.raises(ConfigError, match="No providers configured"):
                load_providers(config_path=str(config_file))
