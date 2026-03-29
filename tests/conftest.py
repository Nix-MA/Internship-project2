import sys
import os
from pathlib import Path

# Automatically inject the project root into sys.path before any tests run
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
