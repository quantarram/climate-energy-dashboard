"""Build both pages: docs/index.html (signals and shock monitor) and docs/archive.html (daily weather panels)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from weatherdash import dashboard, signals_page  # noqa: E402

print("wrote", dashboard.build())
print("wrote", signals_page.build())
