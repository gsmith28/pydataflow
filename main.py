import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pandas  # noqa: F401
except ImportError:
    print("Warning: pandas is required.  Run:  pip install pandas openpyxl")

from app import FlowApp

if __name__ == "__main__":
    app = FlowApp()
    app.run()
