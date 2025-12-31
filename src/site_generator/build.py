"""Site builder that assembles all dashboard artifacts.

Orchestrates:
- Writing latest.json
- Updating history.json
- Saving individual run files
- Generating badges
"""

import json
import os
from pathlib import Path
from typing import Any

from src.site_generator.badges import write_badges
from src.site_generator.history import load_history, append_run, save_history


class SiteGeneratorError(Exception):
    """Raised when site generation fails."""
    pass


def build_site(run_results: dict[str, Any], output_dir: str) -> None:
    """Build all site artifacts from test results.

    Args:
        run_results: Results from test run with structure:
            {
                "timestamp": str,
                "providers": {provider_key: {...}},
                "summary": {...}
            }
        output_dir: Root directory for site data output

    Raises:
        SiteGeneratorError: If results are invalid or write fails
    """
    # Validate results structure
    if "providers" not in run_results:
        raise SiteGeneratorError("Results missing 'providers' key")

    if "timestamp" not in run_results:
        raise SiteGeneratorError("Results missing 'timestamp' key")

    # Create directories
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(output_dir, "runs").mkdir(exist_ok=True)
    Path(output_dir, "badges").mkdir(exist_ok=True)

    # Extract date from timestamp for run filename
    timestamp = run_results["timestamp"]
    date_str = timestamp[:10]  # YYYY-MM-DD

    # 1. Write latest.json
    latest_path = os.path.join(output_dir, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(run_results, f, indent=2)

    # 2. Save individual run file
    run_path = os.path.join(output_dir, "runs", f"{date_str}.json")
    with open(run_path, "w", encoding="utf-8") as f:
        json.dump(run_results, f, indent=2)

    # 3. Update history.json
    history_path = os.path.join(output_dir, "history.json")
    history = load_history(history_path)
    history = append_run(history, run_results)
    save_history(history, history_path)

    # 4. Generate badges
    badges_dir = os.path.join(output_dir, "badges")
    write_badges(run_results.get("providers", {}), badges_dir)
