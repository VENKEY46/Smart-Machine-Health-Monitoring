# Hardware setup

## Parts used in the original project

- ESP32-WROOM-32E DevKitC.
- Grove LSM6DS3 accelerometer/gyroscope, using its acceleration readings.
- Small USB-powered fan.
- A fixed sensor mount on the fan housing.

The original project describes a 0x6A I2C address. Verify your own sensor model
and pin labels before connecting it.

| Sensor connection | ESP32 |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO21 |
| SCL | GPIO22 |

Turn off the hardware before wiring. Attach the sensor to the fixed frame.
Keep it away from rotating blades. Use the supplied fault recording for the
demo; a new physical fault experiment is not required.

## Firmware and network order

1. Complete the recorded-data training steps in the main README.
2. In Arduino IDE, install the ESP32 board package and the
   `Seeed_Arduino_LSM6DS3` and `PubSubClient` libraries.
3. Open this actual sketch file:
   `firmware/Firmware_ESP32_sketch_jul4a/Firmware_ESP32_sketch_jul4a.ino`.
4. Copy `config.example.h` to `config.h` in the same sketch folder.
5. Put your Wi-Fi name and password in `config.h`. Set `MQTT_SERVER` to the
   computer's LAN IPv4 address, found using `ipconfig`. Set
   `MQTT_SERVER_PORT` to the same port as `MQTT_PORT` in `.env` (default 1884).
6. For sensor access, change `MQTT_BIND_ADDRESS` in `.env` from
   `127.0.0.1` to your computer's LAN IPv4 address. This exposes the anonymous
   demonstration broker on that interface. Use only a trusted local network.
   Allow the port in the private-network firewall if needed; do not disable
   the firewall. A university network may block communication between devices.
7. Run `docker compose up -d` to apply the binding change. Keep
   `MQTT_HOST=localhost` only when the broker still binds loopback;
   with a LAN-only binding, set `MQTT_HOST` to that same LAN address so the
   local Python bridge connects to the correct interface.
8. Choose the correct board and COM port in Arduino IDE, then upload.
9. Open Serial Monitor at 115200 baud. Check for `IMU OK` and
   `Connected to MQTT broker`. An IMU initialization error stops sampling.
10. Start `python -m backend.bridge` using the virtual environment.
    Do not run CSV replay on the same topic while the sensor publishes.

The target interval is 10 ms (about 100 Hz). Wi-Fi, I2C and processing may
reduce the actual rate. Check the received-rate panel. The model is a
demonstration based on the supplied recordings; a different mount, fan or
operating condition can change its output.

When returning to local CSV replay, restore `MQTT_BIND_ADDRESS=127.0.0.1`
and `MQTT_HOST=localhost`, then re-run `docker compose up -d`.

## Verification boundary

The firmware edits use a private configuration header, explicit I2C pins,
Wi-Fi recovery and stop-on-sensor-error behavior. They have not been compiled
or uploaded in this review environment because the ESP32 toolchain and
hardware are not available here.
