"""Replay a team CSV recording over MQTT using its recorded timing."""
import argparse
import json
import time
from pathlib import Path

import pandas as pd
from paho.mqtt import client as mqtt

from backend import settings
from backend.bridge import parse_reading


def load_recording(path):
    df = pd.read_csv(path)
    if not {"timestamp", "ax", "ay", "az"}.issubset(df.columns):
        raise ValueError("CSV must contain timestamp, ax, ay and az.")
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601", utc=True, errors="raise")
    if df["timestamp"].isna().any() or df.empty:
        raise ValueError("Recording must have valid timestamps and at least one row.")
    df = df.sort_values("timestamp")
    # Validate before opening a connection, so a malformed file cannot partly replay.
    records = []
    start = df["timestamp"].iloc[0]
    for row in df.itertuples(index=False):
        payload = json.dumps({"ax": row.ax, "ay": row.ay, "az": row.az}, allow_nan=False)
        parse_reading(payload)
        records.append(((row.timestamp - start).total_seconds(), payload))
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=settings.ROOT / "baseline_normal.csv")
    args = parser.parse_args()
    records = load_recording(args.file)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="recording-replay")
    client.connect(settings.MQTT_HOST, settings.MQTT_PORT)
    client.loop_start()
    start = time.monotonic()
    try:
        for index, (offset, payload) in enumerate(records, 1):
            time.sleep(max(0, start + offset - time.monotonic()))
            info = client.publish(settings.MQTT_TOPIC, payload, qos=1)
            info.wait_for_publish(timeout=10)
            if not info.is_published():
                raise TimeoutError("MQTT publication was not acknowledged.")
            if index % 500 == 0:
                print(f"Sent {index}/{len(records)} recorded samples", flush=True)
        print("Replay complete. These were recorded samples, not a live sensor feed.")
    except KeyboardInterrupt:
        print("Replay stopped.")
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
