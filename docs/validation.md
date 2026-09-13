# Reproduced results and review

Reviewed on 13 September 2026 from upstream commit
`7e56ce98afa57346a3ad80114e18742e60373e23`.

## Commands actually executed

- `python -m backend.train_model`
- `python -m backend.validate_model`
- `python -m unittest discover -s tests -v`

A new model was trained from the included baseline CSV. The upstream pickle
was not loaded. The raw team data was not changed.

| Result | Value |
|---|---|
| Baseline windows | 103 |
| Fault-recording windows | 108 |
| Fault-recording windows flagged | 108 / 108 |
| Baseline windows flagged during training-data evaluation | 4 / 103 |
| Baseline decision-score range | -0.165706 to 0.304907 |
| Fault decision-score range | -0.154024 to -0.053002 |
| Mean fault decision score | -0.074664 |
| Automated checks | 14 passed |

The baseline flag rate is measured on training data. It is not a held-out
false-positive estimate. The fault result concerns one recording. It does not
show performance on unseen machines or all fault types.

## Model settings

Isolation Forest uses 200 trees, contamination 0.03 and random seed 42.
Each five-second window needs at least 40 samples. Features are RMS, excess
kurtosis, crest factor, standard deviation and the strongest FFT frequency
of the mean-centred acceleration magnitude.

The magnitude itself is not gravity-corrected. The FFT assumes approximately
regular samples. Offline sample rate is count divided by five seconds; live
sample rate is count divided by the observed window span. Partial edge
windows and network jitter can affect results.

The display index linearly maps the minimum and maximum training decision
scores to 0 and 100 and clips outside that range. A negative decision score
is the model's anomaly decision; fixed index bands such as 50 or 75 are not
validated fault thresholds.

## Review environment

Python 3.12; NumPy 2.3.5; pandas 2.2.3; SciPy 1.17.0; scikit-learn 1.8.0;
joblib 1.5.3; paho-mqtt 2.1.0; influxdb-client 1.50.0; python-dotenv 1.2.3.

The dependency file allows compatible ranges. The generated
`training_report.json` records the core versions used for each local run.
Train and run the model in the same environment.

## What the tests cover

- Known sinusoidal frequency and RMS.
- Constant signals without NaN features.
- Empty, invalid and non-finite samples.
- Malformed MQTT JSON, missing axes and invalid field types.
- Score scaling and invalid ranges.
- Bridge raw/health output using a fake database writer.
- Dropping a partial window after a sample gap.
- CSV timestamp/axis validation and duplicate rejection.
- Local training and evaluation paths.
- Replay timing offsets and export time expressions.

The database writer is mocked in unit tests. Passing these tests is not an
end-to-end Docker test.

## Problems corrected

- Missing requirements and environment templates.
- Imports and model/data paths that failed from the documented directories.
- A firmware path and export filename in the README that did not exist.
- NaN kurtosis from a constant signal.
- Mixed timestamp precision that could reject valid CSV rows.
- A bridge that did not reject non-finite or malformed readings.
- Manual-only Grafana setup with no dashboard file.
- Placeholder tokens inside Python source and a machine-specific firmware IP.
- Claims of a one-command full deployment despite separate Python and hardware steps.
- An MIT link pointing to a missing license file.

## Still to verify on the owner's machine

Docker service startup, Grafana panel rendering, MQTT/InfluxDB integration,
and ESP32 compilation and operation need local verification. New validation
on different operating conditions is needed before relying on the model
for engineering decisions.

## Reference documentation

- [Paho MQTT client](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html)
- [Isolation Forest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html)
- [Model persistence](https://scikit-learn.org/stable/model_persistence.html)
- [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
