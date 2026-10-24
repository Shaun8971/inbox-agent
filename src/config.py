"""Project settings: where files live, and loading triage.yaml.

Every other module imports paths and settings from here, so they're defined in one place.
"""
from pathlib import Path
import yaml

# The project root, worked out from THIS file's location:
#   __file__   = the path of this file (.../inbox-agent/src/config.py)
#   .resolve() = turn it into a full, absolute path
#   .parent    = go up one folder (to src/), .parent again = up to inbox-agent/
# So the code works no matter what the parent folder is called.
ROOT = Path(__file__).resolve().parent.parent

CREDENTIALS_FILE = ROOT / "credentials.json"    # Google app ID card (never committed)
TOKEN_FILE = ROOT / "token.json"                # Saved Gmail login (never committed)
CONFIG_FILE = ROOT / "config" / "triage.yaml"   # Triage settings you can edit


def load_config():
    """Read triage.yaml and return it as Python dictionaries and lists."""
    # safe_load reads plain data only and never runs code hidden in the file
    return yaml.safe_load(CONFIG_FILE.read_text())