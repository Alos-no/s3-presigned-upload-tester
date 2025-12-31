"""Unit tests for history management."""

import json
import os
import tempfile

import pytest

from src.site_generator.history import (
    load_history,
    append_run,
    save_history,
    generate_changelog_entry,
)


class TestLoadHistory:
    """Test history.json loading."""

    def test_load_returns_empty_structure_for_missing_file(self):
        """Missing file should return empty structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            history = load_history(os.path.join(tmpdir, "nonexistent.json"))

            assert history == {
                "last_updated": None,
                "providers": {},
                "changelog": [],
            }

    def test_load_parses_existing_file(self):
        """Existing file should be parsed correctly."""
        existing = {
            "last_updated": "2025-01-15T06:00:00Z",
            "providers": {
                "b2": {
                    "name": "Backblaze B2",
                    "current_status": "pass",
                    "history": [{"date": "2025-01-15", "status": "pass"}],
                }
            },
            "changelog": [],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(existing, f)
            path = f.name

        try:
            history = load_history(path)
            assert history["providers"]["b2"]["name"] == "Backblaze B2"
            assert history["providers"]["b2"]["current_status"] == "pass"
        finally:
            os.unlink(path)

    def test_load_handles_corrupted_file(self):
        """Corrupted file should return empty structure."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            path = f.name

        try:
            history = load_history(path)
            assert history == {
                "last_updated": None,
                "providers": {},
                "changelog": [],
            }
        finally:
            os.unlink(path)

    def test_load_handles_non_dict_json(self):
        """Non-dict JSON should return empty structure."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("[1, 2, 3]")
            path = f.name

        try:
            history = load_history(path)
            assert history == {
                "last_updated": None,
                "providers": {},
                "changelog": [],
            }
        finally:
            os.unlink(path)


class TestAppendRun:
    """Test appending runs to history."""

    def test_append_adds_entry_to_existing_provider(self):
        """Append should add new entry to existing provider."""
        history = {
            "last_updated": "2025-01-08T06:00:00Z",
            "providers": {
                "b2": {
                    "name": "Backblaze B2",
                    "current_status": "pass",
                    "first_tested": "2025-01-01",
                    "history": [{"date": "2025-01-08", "status": "pass"}],
                }
            },
            "changelog": [],
        }

        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {
                "b2": {"name": "Backblaze B2", "status": "pass"},
            },
        }

        updated = append_run(history, run_results)

        assert len(updated["providers"]["b2"]["history"]) == 2
        assert updated["providers"]["b2"]["history"][0]["date"] == "2025-01-15"

    def test_append_creates_new_provider_entry(self):
        """Append should create new provider if first time."""
        history = {
            "last_updated": None,
            "providers": {},
            "changelog": [],
        }

        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {
                "aws": {"name": "AWS S3", "status": "pass"},
            },
        }

        updated = append_run(history, run_results)

        assert "aws" in updated["providers"]
        assert updated["providers"]["aws"]["name"] == "AWS S3"
        assert updated["providers"]["aws"]["current_status"] == "pass"
        assert "2025-01-15" in updated["providers"]["aws"]["first_tested"]

    def test_append_updates_current_status(self):
        """Append should update current_status field."""
        history = {
            "last_updated": "2025-01-08T06:00:00Z",
            "providers": {
                "b2": {
                    "name": "Backblaze B2",
                    "current_status": "pass",
                    "first_tested": "2025-01-01",
                    "history": [{"date": "2025-01-08", "status": "pass"}],
                }
            },
            "changelog": [],
        }

        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {
                "b2": {"name": "Backblaze B2", "status": "fail"},
            },
        }

        updated = append_run(history, run_results)

        assert updated["providers"]["b2"]["current_status"] == "fail"

    def test_append_updates_last_updated_timestamp(self):
        """Append should update last_updated timestamp."""
        history = {
            "last_updated": "2025-01-08T06:00:00Z",
            "providers": {},
            "changelog": [],
        }

        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {},
        }

        updated = append_run(history, run_results)

        assert updated["last_updated"] == "2025-01-15T06:00:00Z"

    def test_append_preserves_historical_entries(self):
        """Append should not remove existing history entries."""
        history = {
            "last_updated": "2025-01-08T06:00:00Z",
            "providers": {
                "b2": {
                    "name": "Backblaze B2",
                    "current_status": "pass",
                    "first_tested": "2025-01-01",
                    "history": [
                        {"date": "2025-01-08", "status": "pass"},
                        {"date": "2025-01-01", "status": "error"},
                    ],
                }
            },
            "changelog": [],
        }

        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {
                "b2": {"name": "Backblaze B2", "status": "pass"},
            },
        }

        updated = append_run(history, run_results)

        assert len(updated["providers"]["b2"]["history"]) == 3

    def test_append_multiple_providers(self):
        """Append should handle multiple providers in single run."""
        history = {
            "last_updated": None,
            "providers": {},
            "changelog": [],
        }

        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {
                "aws": {"name": "AWS S3", "status": "pass"},
                "r2": {"name": "Cloudflare R2", "status": "fail"},
                "b2": {"name": "Backblaze B2", "status": "error"},
            },
        }

        updated = append_run(history, run_results)

        assert len(updated["providers"]) == 3
        assert updated["providers"]["aws"]["current_status"] == "pass"
        assert updated["providers"]["r2"]["current_status"] == "fail"
        assert updated["providers"]["b2"]["current_status"] == "error"


class TestChangelogGeneration:
    """Test changelog generation for status changes."""

    def test_detects_pass_to_fail_transition(self):
        """Changelog should detect pass to fail transition."""
        entry = generate_changelog_entry(
            provider_key="b2",
            provider_name="Backblaze B2",
            old_status="pass",
            new_status="fail",
            timestamp="2025-01-15T06:00:00Z",
        )

        assert entry is not None
        assert entry["provider"] == "b2"
        assert entry["change"] == "fail"
        assert "2025-01-15" in entry["date"]

    def test_detects_fail_to_pass_transition(self):
        """Changelog should detect fail to pass transition."""
        entry = generate_changelog_entry(
            provider_key="r2",
            provider_name="Cloudflare R2",
            old_status="fail",
            new_status="pass",
            timestamp="2025-01-15T06:00:00Z",
        )

        assert entry is not None
        assert entry["change"] == "pass"

    def test_detects_pass_to_error_transition(self):
        """Changelog should detect pass to error transition."""
        entry = generate_changelog_entry(
            provider_key="gcs",
            provider_name="GCS",
            old_status="pass",
            new_status="error",
            timestamp="2025-01-15T06:00:00Z",
        )

        assert entry is not None
        assert entry["change"] == "error"

    def test_detects_error_to_pass_transition(self):
        """Changelog should detect error to pass transition."""
        entry = generate_changelog_entry(
            provider_key="gcs",
            provider_name="GCS",
            old_status="error",
            new_status="pass",
            timestamp="2025-01-15T06:00:00Z",
        )

        assert entry is not None
        assert entry["change"] == "pass"
        assert "recovered" in entry["message"].lower()

    def test_no_entry_when_status_unchanged(self):
        """No changelog entry when status unchanged."""
        entry = generate_changelog_entry(
            provider_key="aws",
            provider_name="AWS S3",
            old_status="pass",
            new_status="pass",
            timestamp="2025-01-15T06:00:00Z",
        )

        assert entry is None

    def test_first_test_generates_entry(self):
        """First test (no old status) should generate changelog entry."""
        entry = generate_changelog_entry(
            provider_key="aws",
            provider_name="AWS S3",
            old_status=None,
            new_status="pass",
            timestamp="2025-01-15T06:00:00Z",
        )

        assert entry is not None
        assert "first" in entry.get("message", "").lower()

    def test_changelog_includes_message(self):
        """Changelog entry should include descriptive message."""
        entry = generate_changelog_entry(
            provider_key="aws",
            provider_name="AWS S3",
            old_status="pass",
            new_status="fail",
            timestamp="2025-01-15T06:00:00Z",
        )

        assert "message" in entry
        assert "AWS S3" in entry["message"]


class TestSaveHistory:
    """Test history saving."""

    def test_save_creates_file(self):
        """save_history should create history file."""
        history = {
            "last_updated": "2025-01-15T06:00:00Z",
            "providers": {"aws": {"name": "AWS S3", "current_status": "pass", "history": []}},
            "changelog": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.json")
            save_history(history, path)

            assert os.path.exists(path)

            with open(path) as f:
                loaded = json.load(f)

            assert loaded["providers"]["aws"]["name"] == "AWS S3"

    def test_save_creates_parent_directory(self):
        """save_history should create parent directory if missing."""
        history = {"last_updated": None, "providers": {}, "changelog": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "nested", "dir", "history.json")
            save_history(history, path)

            assert os.path.exists(path)

    def test_save_overwrites_existing(self):
        """save_history should overwrite existing file."""
        history1 = {"last_updated": "2025-01-08", "providers": {}, "changelog": []}
        history2 = {"last_updated": "2025-01-15", "providers": {}, "changelog": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.json")

            save_history(history1, path)
            save_history(history2, path)

            with open(path) as f:
                loaded = json.load(f)

            assert loaded["last_updated"] == "2025-01-15"


class TestHistoryIntegrationScenarios:
    """Integration tests simulating realistic multi-run scenarios.

    These tests verify that history and changelog are correctly built
    across dozens of runs with various failure/recovery patterns.
    """

    def _make_run(self, date: str, providers: dict[str, str]) -> dict:
        """Helper to create a run result structure.

        Args:
            date: Date string in YYYY-MM-DD format
            providers: Dict of provider_key -> status

        Returns:
            Run result dict
        """
        return {
            "timestamp": f"{date}T06:00:00Z",
            "providers": {
                key: {"name": key.upper(), "status": status}
                for key, status in providers.items()
            },
        }

    def test_simulate_30_runs_with_various_scenarios(self):
        """Simulate 30 runs with failures, recoveries, and transient errors."""
        history = {
            "last_updated": None,
            "providers": {},
            "changelog": [],
        }

        # Define a 30-day scenario:
        # - aws: stable pass throughout
        # - b2: starts failing, recovers on day 10
        # - r2: starts passing, fails day 15-20, recovers
        # - gcs: transient errors on days 5, 12, 25
        runs = [
            # Week 1: Initial tests
            ("2025-01-01", {"aws": "pass", "b2": "fail", "r2": "pass", "gcs": "pass"}),
            ("2025-01-02", {"aws": "pass", "b2": "fail", "r2": "pass", "gcs": "pass"}),
            ("2025-01-03", {"aws": "pass", "b2": "fail", "r2": "pass", "gcs": "pass"}),
            ("2025-01-04", {"aws": "pass", "b2": "fail", "r2": "pass", "gcs": "pass"}),
            ("2025-01-05", {"aws": "pass", "b2": "fail", "r2": "pass", "gcs": "error"}),  # GCS transient
            ("2025-01-06", {"aws": "pass", "b2": "fail", "r2": "pass", "gcs": "pass"}),   # GCS recovers
            ("2025-01-07", {"aws": "pass", "b2": "fail", "r2": "pass", "gcs": "pass"}),
            # Week 2: B2 recovers
            ("2025-01-08", {"aws": "pass", "b2": "fail", "r2": "pass", "gcs": "pass"}),
            ("2025-01-09", {"aws": "pass", "b2": "fail", "r2": "pass", "gcs": "pass"}),
            ("2025-01-10", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),   # B2 recovers
            ("2025-01-11", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),
            ("2025-01-12", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "error"}),  # GCS transient
            ("2025-01-13", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),   # GCS recovers
            ("2025-01-14", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),
            # Week 3: R2 starts failing
            ("2025-01-15", {"aws": "pass", "b2": "pass", "r2": "fail", "gcs": "pass"}),   # R2 fails
            ("2025-01-16", {"aws": "pass", "b2": "pass", "r2": "fail", "gcs": "pass"}),
            ("2025-01-17", {"aws": "pass", "b2": "pass", "r2": "fail", "gcs": "pass"}),
            ("2025-01-18", {"aws": "pass", "b2": "pass", "r2": "fail", "gcs": "pass"}),
            ("2025-01-19", {"aws": "pass", "b2": "pass", "r2": "fail", "gcs": "pass"}),
            ("2025-01-20", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),   # R2 recovers
            ("2025-01-21", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),
            # Week 4: Stable with one more GCS hiccup
            ("2025-01-22", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),
            ("2025-01-23", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),
            ("2025-01-24", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),
            ("2025-01-25", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "error"}),  # GCS transient
            ("2025-01-26", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),   # GCS recovers
            ("2025-01-27", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),
            ("2025-01-28", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),
            ("2025-01-29", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),
            ("2025-01-30", {"aws": "pass", "b2": "pass", "r2": "pass", "gcs": "pass"}),
        ]

        # Execute all runs
        for date, providers in runs:
            run = self._make_run(date, providers)
            history = append_run(history, run)

        # Verify final state
        assert len(history["providers"]) == 4
        assert history["last_updated"] == "2025-01-30T06:00:00Z"

        # All providers should have 30 history entries
        for provider in history["providers"].values():
            assert len(provider["history"]) == 30

        # All should end in pass state
        for provider in history["providers"].values():
            assert provider["current_status"] == "pass"

        # Verify changelog has expected entries
        changelog = history["changelog"]

        # Count by type
        first_tests = [e for e in changelog if "first" in e["message"].lower()]
        failures = [e for e in changelog if e["change"] == "fail" and "first" not in e["message"].lower()]
        recoveries = [e for e in changelog if "recovered" in e["message"].lower() or
                      ("now passing" in e["message"].lower() and "first" not in e["message"].lower())]
        errors = [e for e in changelog if e["change"] == "error"]

        # 4 providers first tested on day 1
        assert len(first_tests) == 4

        # Verify specific changelog events exist
        changelog_messages = [e["message"] for e in changelog]

        # Check for expected transitions
        assert any("B2" in m and "fail" in m.lower() for m in changelog_messages), \
            "Should have B2 first tested as fail"
        assert any("B2" in m and "pass" in m.lower() and "first" not in m.lower() for m in changelog_messages), \
            "Should have B2 recovery"
        assert any("R2" in m and "fail" in m.lower() and "first" not in m.lower() for m in changelog_messages), \
            "Should have R2 failure"
        assert any("R2" in m and ("pass" in m.lower() or "recovered" in m.lower()) and "first" not in m.lower() for m in changelog_messages), \
            "Should have R2 recovery"

    def test_new_provider_added_mid_stream(self):
        """Test adding a new provider after initial runs."""
        history = {
            "last_updated": None,
            "providers": {},
            "changelog": [],
        }

        # First 5 runs with just aws and b2
        for day in range(1, 6):
            run = self._make_run(f"2025-01-{day:02d}", {"aws": "pass", "b2": "pass"})
            history = append_run(history, run)

        assert len(history["providers"]) == 2

        # Day 6: Add r2
        run = self._make_run("2025-01-06", {"aws": "pass", "b2": "pass", "r2": "pass"})
        history = append_run(history, run)

        assert len(history["providers"]) == 3
        assert history["providers"]["r2"]["first_tested"] == "2025-01-06"
        assert len(history["providers"]["r2"]["history"]) == 1

        # Verify first test changelog entry for r2
        r2_first = [e for e in history["changelog"] if e["provider"] == "r2" and "first" in e["message"].lower()]
        assert len(r2_first) == 1
        assert r2_first[0]["date"] == "2025-01-06"

    def test_provider_flapping_detection(self):
        """Test detection of unstable provider that flaps between states."""
        history = {
            "last_updated": None,
            "providers": {},
            "changelog": [],
        }

        # Flapping provider: alternates pass/fail frequently
        statuses = ["pass", "fail", "pass", "fail", "pass", "fail", "pass", "pass", "fail", "pass"]

        for day, status in enumerate(statuses, 1):
            run = self._make_run(f"2025-01-{day:02d}", {"flaky": status})
            history = append_run(history, run)

        # Count transitions
        transitions = [e for e in history["changelog"] if e["provider"] == "flaky"]

        # First test + subsequent changes
        # pass(1st) -> fail -> pass -> fail -> pass -> fail -> pass -> (pass, no change) -> fail -> pass
        # = 1 first + 8 transitions = 9 total
        assert len(transitions) == 9, f"Expected 9 changelog entries, got {len(transitions)}"

    def test_long_running_stable_provider(self):
        """Test provider that stays stable for extended period."""
        history = {
            "last_updated": None,
            "providers": {},
            "changelog": [],
        }

        # 50 consecutive passing runs
        for day in range(1, 51):
            date = f"2025-{(day-1)//28 + 1:02d}-{((day-1) % 28) + 1:02d}"
            run = self._make_run(date, {"stable": "pass"})
            history = append_run(history, run)

        # Should have exactly one changelog entry (first test)
        stable_entries = [e for e in history["changelog"] if e["provider"] == "stable"]
        assert len(stable_entries) == 1
        assert "first" in stable_entries[0]["message"].lower()

        # History should have all 50 entries
        assert len(history["providers"]["stable"]["history"]) == 50

    def test_error_to_fail_transition(self):
        """Test transition from transient error to actual failure."""
        history = {
            "last_updated": None,
            "providers": {},
            "changelog": [],
        }

        runs = [
            ("2025-01-01", {"problematic": "pass"}),
            ("2025-01-02", {"problematic": "error"}),  # Transient error
            ("2025-01-03", {"problematic": "fail"}),   # Now actually failing
            ("2025-01-04", {"problematic": "fail"}),
            ("2025-01-05", {"problematic": "pass"}),   # Eventually fixed
        ]

        for date, providers in runs:
            run = self._make_run(date, providers)
            history = append_run(history, run)

        changelog = [e for e in history["changelog"] if e["provider"] == "problematic"]

        # Should have: first test (pass), error, fail (from error), pass (recovery)
        assert len(changelog) == 4

        changes = [e["change"] for e in reversed(changelog)]  # Reverse to get chronological order
        assert changes == ["pass", "error", "fail", "pass"]

    def test_multiple_providers_simultaneous_failure(self):
        """Test multiple providers failing at the same time."""
        history = {
            "last_updated": None,
            "providers": {},
            "changelog": [],
        }

        runs = [
            ("2025-01-01", {"aws": "pass", "b2": "pass", "r2": "pass"}),
            ("2025-01-02", {"aws": "pass", "b2": "pass", "r2": "pass"}),
            ("2025-01-03", {"aws": "fail", "b2": "fail", "r2": "fail"}),  # All fail!
            ("2025-01-04", {"aws": "pass", "b2": "fail", "r2": "pass"}),  # Partial recovery
            ("2025-01-05", {"aws": "pass", "b2": "pass", "r2": "pass"}),  # Full recovery
        ]

        for date, providers in runs:
            run = self._make_run(date, providers)
            history = append_run(history, run)

        # Check day 3 failures
        day3_failures = [e for e in history["changelog"]
                         if e["date"] == "2025-01-03" and e["change"] == "fail"]
        assert len(day3_failures) == 3

        # Check final state
        for provider in history["providers"].values():
            assert provider["current_status"] == "pass"

    def test_history_ordering_is_newest_first(self):
        """Verify history entries are ordered newest first."""
        history = {
            "last_updated": None,
            "providers": {},
            "changelog": [],
        }

        dates = ["2025-01-01", "2025-01-15", "2025-01-08", "2025-01-22"]

        for date in dates:
            run = self._make_run(date, {"test": "pass"})
            history = append_run(history, run)

        provider_history = history["providers"]["test"]["history"]

        # Most recent should be first
        assert provider_history[0]["date"] == "2025-01-22"
        assert provider_history[1]["date"] == "2025-01-08"
        assert provider_history[2]["date"] == "2025-01-15"
        assert provider_history[3]["date"] == "2025-01-01"

    def test_changelog_ordering_is_newest_first(self):
        """Verify changelog entries are ordered newest first."""
        history = {
            "last_updated": None,
            "providers": {},
            "changelog": [],
        }

        runs = [
            ("2025-01-01", {"test": "pass"}),
            ("2025-01-05", {"test": "fail"}),
            ("2025-01-10", {"test": "pass"}),
        ]

        for date, providers in runs:
            run = self._make_run(date, providers)
            history = append_run(history, run)

        # Newest first
        assert history["changelog"][0]["date"] == "2025-01-10"
        assert history["changelog"][1]["date"] == "2025-01-05"
        assert history["changelog"][2]["date"] == "2025-01-01"
