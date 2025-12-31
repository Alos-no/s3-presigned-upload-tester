#!/usr/bin/env python3
"""
S3 Multipart Upload Content-Length Enforcement Tester

Run this script to test S3-compatible providers for proper Content-Length
enforcement in presigned multipart upload URLs.

Usage:
    python run.py                     # Use config.json
    python run.py -c custom.json      # Use custom config
    python run.py -p b2,r2            # Test specific providers
    python run.py -q                  # Quiet mode (summary only)
    python run.py -j results.json     # Output JSON results
    python run.py --github-actions    # GitHub Actions mode
"""

import sys
from src.cli import main

if __name__ == "__main__":
    sys.exit(main())
