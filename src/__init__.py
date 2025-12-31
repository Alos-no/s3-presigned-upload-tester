"""
S3 Multipart Upload Content-Length Enforcement Tester.

A tool to verify that S3-compatible storage providers correctly enforce
cryptographically-signed Content-Length in presigned multipart upload URLs.
"""

__version__ = "2.0.0"

from src.cli import main

__all__ = ["main", "__version__"]
