"""Unit tests for site building."""

import json
import os
import tempfile

import pytest

from src.site_generator.build import build_site, SiteGeneratorError


class TestBuildSiteDirectories:
    """Test directory creation during build."""

    def test_build_creates_data_directory(self):
        """Build should create data/ directory if missing."""
        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {"aws": {"name": "AWS S3", "status": "pass", "cases": {}}},
            "summary": {"total_providers": 1, "passed": 1, "failed": 0},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "site", "data")
            build_site(run_results, output_dir)

            assert os.path.exists(output_dir)

    def test_build_creates_runs_directory(self):
        """Build should create data/runs/ directory if missing."""
        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {"aws": {"name": "AWS S3", "status": "pass", "cases": {}}},
            "summary": {"total_providers": 1, "passed": 1, "failed": 0},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "data")
            build_site(run_results, output_dir)

            assert os.path.exists(os.path.join(output_dir, "runs"))

    def test_build_creates_badges_directory(self):
        """Build should create badges/ directory if missing."""
        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {"aws": {"name": "AWS S3", "status": "pass", "cases": {}}},
            "summary": {"total_providers": 1, "passed": 1, "failed": 0},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "data")
            build_site(run_results, output_dir)

            assert os.path.exists(os.path.join(output_dir, "badges"))


class TestBuildSiteFiles:
    """Test file generation during build."""

    def test_build_creates_latest_json(self):
        """Build should create latest.json with current run results."""
        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {
                "aws": {"name": "AWS S3", "status": "pass", "cases": {}},
            },
            "summary": {"total_providers": 1, "passed": 1, "failed": 0},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            build_site(run_results, tmpdir)

            latest_path = os.path.join(tmpdir, "latest.json")
            assert os.path.exists(latest_path)

            with open(latest_path) as f:
                data = json.load(f)

            assert data["timestamp"] == "2025-01-15T06:00:00Z"
            assert "aws" in data["providers"]

    def test_build_creates_history_json(self):
        """Build should create history.json."""
        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {"aws": {"name": "AWS S3", "status": "pass", "cases": {}}},
            "summary": {"total_providers": 1, "passed": 1, "failed": 0},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            build_site(run_results, tmpdir)

            history_path = os.path.join(tmpdir, "history.json")
            assert os.path.exists(history_path)

            with open(history_path) as f:
                history = json.load(f)

            assert "aws" in history["providers"]
            assert history["last_updated"] == "2025-01-15T06:00:00Z"

    def test_build_updates_history_json(self):
        """Build should update history.json with new run."""
        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {
                "aws": {"name": "AWS S3", "status": "pass", "cases": {}},
            },
            "summary": {"total_providers": 1, "passed": 1, "failed": 0},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # First build
            build_site(run_results, tmpdir)

            # Second build with different results
            run_results_2 = {
                "timestamp": "2025-01-22T06:00:00Z",
                "providers": {
                    "aws": {"name": "AWS S3", "status": "fail", "cases": {}},
                },
                "summary": {"total_providers": 1, "passed": 0, "failed": 1},
            }
            build_site(run_results_2, tmpdir)

            history_path = os.path.join(tmpdir, "history.json")
            with open(history_path) as f:
                history = json.load(f)

            # Should have 2 history entries for AWS
            assert len(history["providers"]["aws"]["history"]) == 2

    def test_build_saves_individual_run(self):
        """Build should save individual run to runs/YYYY-MM-DD.json."""
        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {"aws": {"name": "AWS S3", "status": "pass", "cases": {}}},
            "summary": {"total_providers": 1, "passed": 1, "failed": 0},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            build_site(run_results, tmpdir)

            run_file = os.path.join(tmpdir, "runs", "2025-01-15.json")
            assert os.path.exists(run_file)

            with open(run_file) as f:
                data = json.load(f)

            assert data["timestamp"] == "2025-01-15T06:00:00Z"

    def test_build_generates_badges(self):
        """Build should generate badge SVGs for each provider."""
        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {
                "aws": {"name": "AWS S3", "status": "pass", "cases": {}},
                "r2": {"name": "Cloudflare R2", "status": "fail", "cases": {}},
            },
            "summary": {"total_providers": 2, "passed": 1, "failed": 1},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            build_site(run_results, tmpdir)

            assert os.path.exists(os.path.join(tmpdir, "badges", "aws.svg"))
            assert os.path.exists(os.path.join(tmpdir, "badges", "r2.svg"))
            assert os.path.exists(os.path.join(tmpdir, "badges", "overall.svg"))


class TestBuildSiteErrorHandling:
    """Test error handling in site building."""

    def test_build_raises_on_missing_providers(self):
        """Build should raise error when providers key missing."""
        invalid_results = {"timestamp": "2025-01-15T06:00:00Z"}

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(SiteGeneratorError):
                build_site(invalid_results, tmpdir)

    def test_build_raises_on_missing_timestamp(self):
        """Build should raise error when timestamp missing."""
        invalid_results = {"providers": {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(SiteGeneratorError):
                build_site(invalid_results, tmpdir)

    def test_build_handles_empty_providers(self):
        """Build should handle empty providers dict."""
        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {},
            "summary": {"total_providers": 0, "passed": 0, "failed": 0},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Should not raise
            build_site(run_results, tmpdir)

            # Should still create overall badge
            assert os.path.exists(os.path.join(tmpdir, "badges", "overall.svg"))


class TestBuildSiteIntegration:
    """Integration tests for the full site generation workflow."""

    def test_full_workflow_all_pass(self):
        """Full workflow with all providers passing."""
        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {
                "aws": {
                    "name": "AWS S3",
                    "status": "pass",
                    "cases": {
                        "case_1": {"status": "pass", "expected": "rejected", "actual": "rejected"},
                        "case_7": {"status": "pass", "expected": "accepted", "actual": "accepted"},
                    },
                    "duration_seconds": 45.2,
                },
                "r2": {
                    "name": "Cloudflare R2",
                    "status": "pass",
                    "cases": {
                        "case_1": {"status": "pass", "expected": "rejected", "actual": "rejected"},
                        "case_7": {"status": "pass", "expected": "accepted", "actual": "accepted"},
                    },
                    "duration_seconds": 38.7,
                },
            },
            "summary": {"total_providers": 2, "passed": 2, "failed": 0},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            build_site(run_results, tmpdir)

            # Verify all files created
            assert os.path.exists(os.path.join(tmpdir, "latest.json"))
            assert os.path.exists(os.path.join(tmpdir, "history.json"))
            assert os.path.exists(os.path.join(tmpdir, "runs", "2025-01-15.json"))
            assert os.path.exists(os.path.join(tmpdir, "badges", "aws.svg"))
            assert os.path.exists(os.path.join(tmpdir, "badges", "r2.svg"))
            assert os.path.exists(os.path.join(tmpdir, "badges", "overall.svg"))

            # Verify badges are green
            with open(os.path.join(tmpdir, "badges", "aws.svg")) as f:
                aws_badge = f.read()
            assert "#4c1" in aws_badge or "#44cc11" in aws_badge

            # Verify overall badge shows 2/2
            with open(os.path.join(tmpdir, "badges", "overall.svg")) as f:
                overall = f.read()
            assert "2/2" in overall or "2 of 2" in overall

    def test_full_workflow_mixed_results(self):
        """Full workflow with mixed results."""
        run_results = {
            "timestamp": "2025-01-15T06:00:00Z",
            "providers": {
                "aws": {
                    "name": "AWS S3",
                    "status": "pass",
                    "cases": {},
                    "duration_seconds": 45.2,
                },
                "r2": {
                    "name": "Cloudflare R2",
                    "status": "fail",
                    "cases": {},
                    "duration_seconds": 38.7,
                },
                "gcs": {
                    "name": "GCS",
                    "status": "error",
                    "cases": {},
                    "duration_seconds": 5.1,
                    "error_message": "Connection timeout",
                },
            },
            "summary": {"total_providers": 3, "passed": 1, "failed": 1},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            build_site(run_results, tmpdir)

            # Verify badges have correct colors
            with open(os.path.join(tmpdir, "badges", "aws.svg")) as f:
                assert "#4c1" in f.read() or "#44cc11" in f.read()

            with open(os.path.join(tmpdir, "badges", "r2.svg")) as f:
                assert "#e05d44" in f.read()

            with open(os.path.join(tmpdir, "badges", "gcs.svg")) as f:
                assert "#e05d44" in f.read()  # Error is now red

            # Overall should be red (has failure)
            with open(os.path.join(tmpdir, "badges", "overall.svg")) as f:
                assert "#e05d44" in f.read()

    def test_history_accumulates_over_runs(self):
        """History should accumulate across multiple runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First run - all pass
            run1 = {
                "timestamp": "2025-01-08T06:00:00Z",
                "providers": {"aws": {"name": "AWS S3", "status": "pass", "cases": {}}},
                "summary": {"total_providers": 1, "passed": 1, "failed": 0},
            }
            build_site(run1, tmpdir)

            # Second run - fail
            run2 = {
                "timestamp": "2025-01-15T06:00:00Z",
                "providers": {"aws": {"name": "AWS S3", "status": "fail", "cases": {}}},
                "summary": {"total_providers": 1, "passed": 0, "failed": 1},
            }
            build_site(run2, tmpdir)

            # Third run - pass again
            run3 = {
                "timestamp": "2025-01-22T06:00:00Z",
                "providers": {"aws": {"name": "AWS S3", "status": "pass", "cases": {}}},
                "summary": {"total_providers": 1, "passed": 1, "failed": 0},
            }
            build_site(run3, tmpdir)

            # Verify history
            with open(os.path.join(tmpdir, "history.json")) as f:
                history = json.load(f)

            aws_history = history["providers"]["aws"]["history"]
            assert len(aws_history) == 3

            # Most recent first
            assert aws_history[0]["status"] == "pass"
            assert aws_history[1]["status"] == "fail"
            assert aws_history[2]["status"] == "pass"

    def test_changelog_captures_status_changes(self):
        """Changelog should capture status changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First run - pass
            run1 = {
                "timestamp": "2025-01-08T06:00:00Z",
                "providers": {"aws": {"name": "AWS S3", "status": "pass", "cases": {}}},
                "summary": {"total_providers": 1, "passed": 1, "failed": 0},
            }
            build_site(run1, tmpdir)

            # Second run - fail (status change!)
            run2 = {
                "timestamp": "2025-01-15T06:00:00Z",
                "providers": {"aws": {"name": "AWS S3", "status": "fail", "cases": {}}},
                "summary": {"total_providers": 1, "passed": 0, "failed": 1},
            }
            build_site(run2, tmpdir)

            # Verify changelog
            with open(os.path.join(tmpdir, "history.json")) as f:
                history = json.load(f)

            # Should have changelog entries
            assert len(history["changelog"]) >= 1

            # Should have entry for the fail transition
            fail_entry = next(
                (e for e in history["changelog"] if e.get("change") == "fail"),
                None
            )
            assert fail_entry is not None
            assert fail_entry["provider"] == "aws"
