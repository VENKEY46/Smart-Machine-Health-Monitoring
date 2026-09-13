import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd

from backend.bridge import Bridge, parse_reading, to_health_score
from backend.InfluxDB_Generate_CSV_Script import time_expression
from backend.replay_recording import load_recording
from backend.train_model import train
from backend.validate_model import evaluate
from feature_extraction import compute_window_features, extract_features


class FeatureTests(unittest.TestCase):
    def test_known_sine_frequency(self):
        t = np.arange(500) / 100
        features = compute_window_features(1 + 0.2 * np.sin(2 * np.pi * 10 * t), 100)
        self.assertAlmostEqual(features[4], 10)
        self.assertAlmostEqual(features[0], np.sqrt(1.02))

    def test_constant_signal_is_finite(self):
        features = compute_window_features(np.ones(500), 100)
        self.assertTrue(np.isfinite(features).all())
        self.assertEqual(features[1], 0)
        self.assertEqual(features[4], 0)

    def test_bad_samples_and_rate_are_rejected(self):
        for values, rate in [([], 100), ([1, np.nan], 100), ([1, 2], 0), ([1, 2], np.inf)]:
            with self.subTest(values=values, rate=rate), self.assertRaises(ValueError):
                compute_window_features(values, rate)


class MessageTests(unittest.TestCase):
    def test_valid_payload(self):
        self.assertEqual(parse_reading('{"ax": 0.1, "ay": -1, "az": 0}'), [0.1, -1, 0])

    def test_bad_payloads(self):
        for raw in ['[]', 'null', '{', '{"ax":0}',
                    '{"ax":true,"ay":1,"az":0}',
                    '{"ax":"1","ay":1,"az":0}',
                    '{"ax":NaN,"ay":1,"az":0}']:
            with self.subTest(raw=raw), self.assertRaises((ValueError, TypeError)):
                parse_reading(raw)

    def test_index_clips_and_checks_range(self):
        self.assertEqual(to_health_score(-2, -1, 1), 0)
        self.assertEqual(to_health_score(0, -1, 1), 50)
        self.assertEqual(to_health_score(2, -1, 1), 100)
        with self.assertRaises(ValueError):
            to_health_score(1, 1, 1)

    def test_bridge_emits_raw_and_health_points(self):
        writer, model = Mock(), Mock()
        model.decision_function.return_value = np.array([-0.1])
        bridge = Bridge(writer, model, [-0.2, 0.2])
        for i in range(501):
            bridge.process(json.dumps({"ax": 0, "ay": 1 + 0.1 * np.sin(i), "az": 0}), i / 100)
        self.assertEqual(writer.write.call_count, 502)
        line = writer.write.call_args.kwargs["record"].to_line_protocol()
        self.assertIn("health ", line)
        self.assertIn("anomaly=1i", line)
        self.assertIn("score=25", line)
        self.assertEqual(len(bridge.buffer), 0)

    def test_invalid_message_does_not_write(self):
        writer = Mock()
        bridge = Bridge(writer, Mock(), [-1, 1])
        message = Mock(payload=b'{"ax":NaN,"ay":0,"az":1}')
        bridge.on_message(None, None, message)
        writer.write.assert_not_called()

    def test_gap_discards_old_window(self):
        bridge = Bridge(Mock(), Mock(), [-1, 1])
        raw = '{"ax":0,"ay":1,"az":0}'
        bridge.process(raw, 0)
        bridge.process(raw, 3)
        self.assertEqual(len(bridge.buffer), 1)


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.path = self.root / "recording.csv"
        t = np.arange(1500) / 100
        self.df = pd.DataFrame({"timestamp": pd.Timestamp("2026-01-01", tz="UTC") + pd.to_timedelta(t, unit="s"),
                                "ax": 0.1 * np.sin(t * 20), "ay": 1 + 0.1 * np.sin(t * 60), "az": 0})
        self.df.to_csv(self.path, index=False)

    def tearDown(self):
        self.directory.cleanup()

    def test_three_windows_and_training_paths(self):
        self.assertEqual(extract_features(self.path).shape, (3, 5))
        output = self.root / "models"
        report = train(self.path, output)
        self.assertEqual(report["baseline_windows"], 3)
        result = evaluate(self.path, output / "isolation_forest_model.pkl")
        self.assertEqual(result["windows"], 3)
        self.assertTrue((output / "training_report.json").exists())

    def test_csv_invalid_timestamp_and_axis(self):
        for column, bad in [("timestamp", "bad date"), ("ax", float("nan"))]:
            df = self.df.copy()
            df[column] = df[column].astype(object)
            df.loc[0, column] = bad
            df.to_csv(self.path, index=False)
            with self.subTest(column=column), self.assertRaises(ValueError):
                extract_features(self.path)

    def test_duplicate_timestamp_is_rejected(self):
        self.df.loc[1, "timestamp"] = self.df.loc[0, "timestamp"]
        self.df.to_csv(self.path, index=False)
        with self.assertRaises(ValueError):
            extract_features(self.path)

    def test_replay_preserves_recorded_offsets(self):
        rows = load_recording(self.path)
        self.assertEqual(len(rows), 1500)
        self.assertAlmostEqual(rows[-1][0], 14.99)
        self.assertEqual(len(parse_reading(rows[0][1])), 3)

    def test_flux_time_expressions(self):
        self.assertEqual(time_expression("-10m"), "-10m")
        self.assertEqual(time_expression("now()"), "now()")
        self.assertTrue(time_expression("2026-01-01T00:00:00Z").startswith("time(v:"))
        with self.assertRaises(ValueError):
            time_expression('now()) |> drop(columns: ["ax"])')


if __name__ == "__main__":
    unittest.main()
