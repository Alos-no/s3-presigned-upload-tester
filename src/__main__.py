"""Entry point for running as a module: python -m src"""

import sys
from src.cli import main

if __name__ == "__main__":
    sys.exit(main())
