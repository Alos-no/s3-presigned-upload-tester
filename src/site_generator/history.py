"""History management for tracking provider status over time.

Handles loading, updating, and saving history.json with:
- Per-provider historical status entries
- Changelog of status changes
"""

import json
import os
from datetime import datetime
from typing import Any


def load_history(path: str) -> dict[str, Any]:
    """Load history from JSON file.

    Args:
        path: Path to history.json file

    Returns:
        History dict with structure:
        {
            "last_updated": str | None,
            "providers": {provider_key: {...}},
            "changelog": [...]
        }

    If file doesn't exist or is corrupted, returns empty structure.
    """
    if not os.path.exists(path):
        return {
            "last_updated": None,
            "providers": {},
            "changelog": [],
        }

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        # Validate basic structure
        if not isinstance(data, dict):
            return {
                "last_updated": None,
                "providers": {},
                "changelog": [],
            }

        # Ensure required keys exist
        return {
            "last_updated": data.get("last_updated"),
            "providers": data.get("providers", {}),
            "changelog": data.get("changelog", []),
        }

    except (json.JSONDecodeError, OSError):
        # Return empty structure for corrupted/unreadable files
        return {
            "last_updated": None,
            "providers": {},
            "changelog": [],
        }


def append_run(history: dict[str, Any], run_results: dict[str, Any]) -> dict[str, Any]:
    """Append a new test run to history.

    Args:
        history: Current history dict
        run_results: Results from test run with structure:
            {
                "timestamp": str,
                "providers": {provider_key: {"name": str, "status": str, ...}}
            }

    Returns:
        Updated history dict
    """
    timestamp = run_results.get("timestamp", datetime.now().isoformat())
    date_str = timestamp[:10]  # YYYY-MM-DD

    # Process each provider in the run
    for provider_key, provider_data in run_results.get("providers", {}).items():
        new_status = provider_data.get("status", "error")
        provider_name = provider_data.get("name", provider_key)

        if provider_key not in history["providers"]:
            # New provider - create entry
            history["providers"][provider_key] = {
                "name": provider_name,
                "current_status": new_status,
                "first_tested": date_str,
                "history": [],
            }
            old_status = None
        else:
            old_status = history["providers"][provider_key].get("current_status")
            history["providers"][provider_key]["current_status"] = new_status

        # Add history entry (most recent first)
        history["providers"][provider_key]["history"].insert(0, {
            "date": date_str,
            "status": new_status,
        })

        # Generate changelog entry if status changed
        changelog_entry = generate_changelog_entry(
            provider_key=provider_key,
            provider_name=provider_name,
            old_status=old_status,
            new_status=new_status,
            timestamp=timestamp,
        )

        if changelog_entry:
            history["changelog"].insert(0, changelog_entry)

    # Update last_updated
    history["last_updated"] = timestamp

    return history


def generate_changelog_entry(
    provider_key: str,
    provider_name: str,
    old_status: str | None,
    new_status: str,
    timestamp: str,
) -> dict[str, str] | None:
    """Generate a changelog entry for a status change.

    Args:
        provider_key: Provider identifier
        provider_name: Display name
        old_status: Previous status (None if first test)
        new_status: New status
        timestamp: ISO timestamp of the change

    Returns:
        Changelog entry dict or None if no change
    """
    date_str = timestamp[:10]

    # First test for this provider
    if old_status is None:
        return {
            "date": date_str,
            "provider": provider_key,
            "change": new_status,
            "message": f"{provider_name} first tested - {new_status}",
        }

    # No change
    if old_status == new_status:
        return None

    # Status changed - generate appropriate message
    messages = {
        ("pass", "fail"): f"{provider_name} now failing compliance tests",
        ("pass", "error"): f"{provider_name} - transient error occurred",
        ("fail", "pass"): f"{provider_name} now passing all compliance tests",
        ("fail", "error"): f"{provider_name} - transient error (was failing)",
        ("error", "pass"): f"{provider_name} recovered - now passing",
        ("error", "fail"): f"{provider_name} now failing (was error state)",
    }

    message = messages.get(
        (old_status, new_status),
        f"{provider_name} status changed from {old_status} to {new_status}"
    )

    return {
        "date": date_str,
        "provider": provider_key,
        "change": new_status,
        "message": message,
    }


def save_history(history: dict[str, Any], path: str) -> None:
    """Save history to JSON file.

    Args:
        history: History dict to save
        path: Path to write history.json
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
