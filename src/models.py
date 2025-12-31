"""Data models for the S3 enforcement tester."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ResultStatus(Enum):
    """Status of a test case or provider."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


@dataclass
class ProviderConfig:
    """Configuration for an S3-compatible provider."""

    key: str
    provider_name: str
    endpoint_url: str
    aws_access_key_id: str
    aws_secret_access_key: str
    region_name: str
    bucket_name: str
    addressing_style: str = "path"
    enabled: bool = True


@dataclass
class CaseResult:
    """Result of a single test case execution."""

    case_id: str
    case_name: str
    status: ResultStatus
    expected: str
    actual: str
    error_message: Optional[str] = None


@dataclass
class ProviderResult:
    """Aggregated results for a single provider."""

    provider_key: str
    provider_name: str
    status: ResultStatus
    cases: dict[str, CaseResult] = field(default_factory=dict)
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
