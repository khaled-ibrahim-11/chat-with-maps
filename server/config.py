"""Project paths, resolved independently of the working directory."""

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
CLIENT_DIR = PROJECT_DIR / "client"
DATA_PATH = PROJECT_DIR / "data" / "dubai-pois.geojson"
