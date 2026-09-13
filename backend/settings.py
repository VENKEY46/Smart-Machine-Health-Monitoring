"""Shared paths and local configuration, independent of the working directory."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
MODEL_DIR = ROOT / "models" / "generated"
MODEL_PATH = MODEL_DIR / "isolation_forest_model.pkl"
SCORE_PATH = MODEL_DIR / "score_range.npy"
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8087")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = os.getenv("INFLUX_ORG", "smart-machine")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "vibration")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1884"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensors/fan1/vibration")


def require_influx_token():
    if not INFLUX_TOKEN or INFLUX_TOKEN.startswith("replace-"):
        raise ValueError("Set INFLUX_TOKEN in the root .env file before running the live demo.")
