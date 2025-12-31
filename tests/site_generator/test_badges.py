"""Unit tests for badge generation."""

import os
import tempfile

import pytest

from src.site_generator.badges import (
    generate_badge,
    generate_overall_badge,
    write_badges,
)


class TestBadgeGeneration:
    """Test SVG badge generation."""

    def test_pass_status_generates_green_badge(self):
        """Pass status should generate green (#4c1) badge."""
        svg = generate_badge("AWS S3", "pass")

        assert "#4c1" in svg or "#44cc11" in svg  # Green color
        assert "AWS S3" in svg
        assert "Compliant" in svg or "pass" in svg.lower()

    def test_fail_status_generates_red_badge(self):
        """Fail status should generate red (#e05d44) badge."""
        svg = generate_badge("Cloudflare R2", "fail")

        assert "#e05d44" in svg  # Red color
        assert "Cloudflare R2" in svg or "R2" in svg
        assert "Non-Compliant" in svg or "fail" in svg.lower()

    def test_error_status_generates_red_badge(self):
        """Error status should generate red (#e05d44) badge."""
        svg = generate_badge("GCS", "error")

        assert "#e05d44" in svg  # Red color (same as fail)
        assert "GCS" in svg
        assert "Error" in svg or "error" in svg.lower()

    def test_badge_is_valid_svg(self):
        """Badge should be valid SVG markup."""
        svg = generate_badge("Test Provider", "pass")

        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        assert "xmlns" in svg

    def test_badge_escapes_special_characters(self):
        """Badge should escape HTML special characters in provider name."""
        svg = generate_badge("Test <Provider> & Co.", "pass")

        # Should not contain unescaped special chars
        assert "<Provider>" not in svg
        assert "&lt;" in svg or "Test" in svg  # Either escaped or simplified


class TestOverallBadge:
    """Test overall summary badge generation."""

    def test_overall_badge_shows_passing_count(self):
        """Overall badge should show X/Y Passing format."""
        results = {
            "aws": {"status": "pass"},
            "r2": {"status": "pass"},
            "b2": {"status": "fail"},
            "gcs": {"status": "error"},
        }

        svg = generate_overall_badge(results)

        assert "2/4" in svg or "2 of 4" in svg
        assert "Passing" in svg or "passing" in svg

    def test_overall_badge_all_pass_is_green(self):
        """Overall badge should be green when all pass."""
        results = {
            "aws": {"status": "pass"},
            "r2": {"status": "pass"},
        }

        svg = generate_overall_badge(results)

        assert "#4c1" in svg or "#44cc11" in svg

    def test_overall_badge_any_fail_is_red(self):
        """Overall badge should be red when any provider fails."""
        results = {
            "aws": {"status": "pass"},
            "r2": {"status": "fail"},
        }

        svg = generate_overall_badge(results)

        assert "#e05d44" in svg

    def test_overall_badge_only_errors_is_red(self):
        """Overall badge should be red when only errors (no fails)."""
        results = {
            "aws": {"status": "pass"},
            "gcs": {"status": "error"},
        }

        svg = generate_overall_badge(results)

        assert "#e05d44" in svg

    def test_overall_badge_empty_results(self):
        """Overall badge should handle empty results."""
        svg = generate_overall_badge({})

        assert "0/0" in svg
        assert svg.startswith("<svg")


class TestWriteBadges:
    """Test badge file writing."""

    def test_write_badges_creates_files(self):
        """write_badges should create SVG files for each provider."""
        results = {
            "aws": {"name": "AWS S3", "status": "pass"},
            "r2": {"name": "Cloudflare R2", "status": "fail"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            write_badges(results, tmpdir)

            assert os.path.exists(os.path.join(tmpdir, "aws.svg"))
            assert os.path.exists(os.path.join(tmpdir, "r2.svg"))
            assert os.path.exists(os.path.join(tmpdir, "overall.svg"))

    def test_write_badges_creates_directory(self):
        """write_badges should create output directory if missing."""
        results = {"aws": {"name": "AWS S3", "status": "pass"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "nested", "badges")
            write_badges(results, output_dir)

            assert os.path.exists(output_dir)
            assert os.path.exists(os.path.join(output_dir, "aws.svg"))

    def test_write_badges_svg_content_valid(self):
        """Written SVG files should contain valid SVG content."""
        results = {"aws": {"name": "AWS S3", "status": "pass"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            write_badges(results, tmpdir)

            with open(os.path.join(tmpdir, "aws.svg")) as f:
                content = f.read()

            assert content.startswith("<svg")
            assert content.endswith("</svg>")
            assert "AWS S3" in content
