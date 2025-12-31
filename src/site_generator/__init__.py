"""Site generator modules for building the dashboard.

Exports:
- build_site: Main function to generate all site artifacts
- SiteGeneratorError: Exception for build failures
"""

from src.site_generator.build import build_site, SiteGeneratorError
from src.site_generator.badges import generate_badge, generate_overall_badge, write_badges
from src.site_generator.history import load_history, append_run, save_history

__all__ = [
    "build_site",
    "SiteGeneratorError",
    "generate_badge",
    "generate_overall_badge",
    "write_badges",
    "load_history",
    "append_run",
    "save_history",
]
