import sys
import os

# Ensure the project root is on the path so `src` package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.main import app  # noqa: F401 — Vercel discovers the `app` object
