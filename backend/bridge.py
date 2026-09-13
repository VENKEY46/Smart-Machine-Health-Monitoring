"""Receive vibration JSON, queue InfluxDB writes, and score five-second windows."""
import json
import logging
import math
import time
from collections import deque

import joblib
import numpy as np
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import WriteOptions
from paho.mqtt import client as mqtt

from backend import settings
from feature_extraction import compute_window_features

LOG = logging.getLogger(__name__)
WINDOW_SECONDS = 5.0
MIN_SAMPLES = 40


def parse_reading(raw):
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("MQTT payload must be a JSON object.")
    values = []
    for axis in ("ax", "ay", "az"):
        value = payload.get(axis)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{axis} must be a finite number.")
        if not math.isfinite(value):
            raise ValueError(f"{axis} must be a finite number.")
        values.append(float(value))
    if not math.isfinite(math.hypot(*values)):
        raise ValueError("Acceleration magnitude is too large.")
    return values


def to_health_score(raw_score, score_min, score_max):
    # This is a baseline-relative display index, not a failure probability.
    if not all(np.isfinite(v) for v in (raw_score, score_min, score_max)):
        raise ValueError("Model scores must be finite.")
    if score_max <= score_min:
        raise ValueError("Baseline score range must have a positive width.")
    return float(np.clip((raw_score - score_min) / (score_max - score_min), 0, 1) * 100)


class Bridge:
    def __init__(self, write_api, model, score_range):
        self.write_api = write_api
        self.model = model
        self.score_min, self.score_max = score_range
        to_health_score(self.score_min, self.score_min, self.score_max)
        self.buffer = deque()
        self.previous_arrival = None

    def process(self, raw, arrival=None):
        ax, ay, az = parse_reading(raw)
        now = time.monotonic() if arrival is None else arrival
        # A network gap invalidates the current scoring window.
        if self.previous_arrival is not None and now - self.previous_arrival > 1.0:
            self.buffer.clear()
            LOG.warning("Sample gap: restarting the scoring window.")
        self.previous_arrival = now
        timestamp = time.time_ns()
        point = (Point("vibration").field("ax", ax).field("ay", ay).field("az", az)
                 .time(timestamp, WritePrecision.NS))
        self.write_api.write(bucket=settings.INFLUX_BUCKET, org=settings.INFLUX_ORG, record=point)
        self.buffer.append((now, math.hypot(ax, ay, az)))
        if len(self.buffer) > 10000:
            self.buffer.clear()
            raise ValueError("Too many samples in one window; check the source rate.")
        elapsed = now - self.buffer[0][0]
        if elapsed >= WINDOW_SECONDS:
            samples = np.array([value for _, value in self.buffer])
            self.buffer.clear()
            if len(samples) < MIN_SAMPLES:
                LOG.warning("Skipped a window with only %s samples.", len(samples))
                return
            fs_actual = len(samples) / elapsed
            features = compute_window_features(samples, fs_actual)
            raw_score = float(self.model.decision_function([features])[0])
            health = to_health_score(raw_score, self.score_min, self.score_max)
            point = (Point("health").field("score", health).field("decision_score", raw_score)
                     .field("anomaly", int(raw_score < 0)).field("sample_rate_hz", fs_actual)
                     .time(timestamp, WritePrecision.NS))
            self.write_api.write(bucket=settings.INFLUX_BUCKET, org=settings.INFLUX_ORG, record=point)
            LOG.info("Queued window: %s samples, %.1f Hz, index %.1f, anomaly=%s",
                     len(samples), fs_actual, health, raw_score < 0)

    def on_message(self, client, userdata, message):
        try:
            self.process(message.payload)
        except (ValueError, TypeError, UnicodeError, OverflowError) as exc:
            self.buffer.clear()
            LOG.warning("Rejected message or window: %s", exc)
        except Exception:
            self.buffer.clear()
            LOG.exception("Processing failed; this prototype has no durable retry queue.")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings.require_influx_token()
    if not settings.MODEL_PATH.exists() or not settings.SCORE_PATH.exists():
        raise FileNotFoundError("Run python -m backend.train_model before starting the bridge.")
    # Only locally generated models are loaded by default; upstream binaries are preserved as reference.
    model = joblib.load(settings.MODEL_PATH)
    score_range = np.load(settings.SCORE_PATH, allow_pickle=False)
    with InfluxDBClient(url=settings.INFLUX_URL, token=settings.INFLUX_TOKEN,
                        org=settings.INFLUX_ORG) as influx:
        write_api = influx.write_api(
            write_options=WriteOptions(batch_size=50, flush_interval=200),
            error_callback=lambda conf, data, exc: LOG.error("InfluxDB batch write failed: %s", exc))
        bridge = Bridge(write_api, model, score_range)
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="machine-health-bridge")

        def on_connect(client, userdata, flags, reason_code, properties):
            if reason_code == 0:
                client.subscribe(settings.MQTT_TOPIC)
                LOG.info("Subscribed to %s", settings.MQTT_TOPIC)
            else:
                LOG.error("MQTT connection failed: %s", reason_code)

        client.on_connect = on_connect
        client.on_message = bridge.on_message
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        try:
            client.connect(settings.MQTT_HOST, settings.MQTT_PORT)
            client.loop_forever()
        except KeyboardInterrupt:
            LOG.info("Stopping bridge and flushing pending writes.")
        finally:
            client.disconnect()
            write_api.close()


if __name__ == "__main__":
    main()
