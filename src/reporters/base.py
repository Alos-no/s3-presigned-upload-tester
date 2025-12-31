"""Base reporter interface."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import CaseResult, ProviderResult


class Reporter(ABC):
    """Abstract base class for test result reporters."""

    @abstractmethod
    def on_case_start(self, provider_name: str, case_id: str) -> None:
        """Called when a test case starts."""
        pass

    @abstractmethod
    def on_case_complete(self, provider_name: str, result: "CaseResult") -> None:
        """Called when a test case completes."""
        pass

    @abstractmethod
    def on_provider_start(self, provider_name: str) -> None:
        """Called when testing begins for a provider."""
        pass

    @abstractmethod
    def on_provider_complete(self, result: "ProviderResult") -> None:
        """Called when testing completes for a provider."""
        pass

    @abstractmethod
    def on_run_complete(self, results: dict[str, "ProviderResult"]) -> None:
        """Called when all testing is complete."""
        pass
