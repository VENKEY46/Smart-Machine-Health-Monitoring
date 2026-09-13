"""Export raw vibration points from InfluxDB to a training-compatible CSV."""
import argparse
import json
import re
from pathlib import Path

import pandas as pd
from influxdb_client import InfluxDBClient

from backend import settings


def time_expression(value):
    if value == "now()" or re.fullmatch(r"-[1-9][0-9]*(ms|s|m|h|d|w)", value):
        return value
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp) or timestamp.tzinfo is None:
        raise ValueError("Use a duration such as -10m or an ISO timestamp with a timezone.")
    return "time(v: " + json.dumps(timestamp.isoformat()) + ")"


def export_range(start, stop, outfile):
    settings.require_influx_token()
    query = f'''
    from(bucket: {json.dumps(settings.INFLUX_BUCKET)})
      |> range(start: {time_expression(start)}, stop: {time_expression(stop)})
      |> filter(fn: (r) => r._measurement == "vibration")
      |> filter(fn: (r) => r._field == "ax" or r._field == "ay" or r._field == "az")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> keep(columns: ["_time", "ax", "ay", "az"])
    '''
    with InfluxDBClient(url=settings.INFLUX_URL, token=settings.INFLUX_TOKEN,
                        org=settings.INFLUX_ORG) as client:
        result = client.query_api().query_data_frame(query)
    if isinstance(result, list):
        result = pd.concat(result, ignore_index=True) if result else pd.DataFrame()
    if result is None or result.empty:
        print("No data returned. Check the time range and bridge output.")
        return
    df = result.rename(columns={"_time": "timestamp"})[["timestamp", "ax", "ay", "az"]]
    outfile = Path(outfile)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    df.sort_values("timestamp").to_csv(outfile, index=False)
    print(f"Saved {len(df)} rows to {outfile}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="-10m")
    parser.add_argument("--stop", default="now()")
    parser.add_argument("--output", type=Path, default=settings.ROOT / "output" / "export.csv")
    args = parser.parse_args()
    export_range(args.start, args.stop, args.output)


if __name__ == "__main__":
    main()
