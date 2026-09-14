# Signed NodeMCU Firmware

This firmware reads a physical DS18B20 on NodeMCU pin `D4` (`GPIO2`) and signs
every telemetry reading with a device-specific ECDSA P-256 private key. The
gateway enrolls the public key on first contact and rejects readings whose
signatures do not verify.

Install the Arduino **OneWire** and **DallasTemperature** libraries before
building. Wire the sensor data pin to `D4`, add a 4.7 kΩ pull-up from data to
`3.3V`, and power the sensor from `3.3V`. The built-in NodeMCU LED also uses
GPIO2, so this firmware deliberately does not drive that LED.

Disconnected sensors, the DS18B20 power-on value `85 °C`, and values outside
the sensor's specified range are rejected and are never signed.

Telemetry schema 3 also signs a per-boot ID, the ESP8266 reset reason, and the
enclosure tamper state. Old schema-2 batches remain verifiable.

## Optional enclosure switch

The firmware defaults to `kTamperPin = -1`, so no GPIO is used. When a
normally-closed switch between GPIO and GND is installed, set `kTamperPin` in
`nodemcu_signed.ino` to a free pin such as `D5`. The internal pull-up keeps a
closed circuit at LOW; opening the enclosure raises the input and produces
`tamper_open: true` in every signed reading.

## Generate the Device Key

From the repository root on Ubuntu:

```bash
python3 -m venv .venv
.venv/bin/pip install -r gateway/requirements.txt
.venv/bin/python -m gateway.device_keys \
  --output firmware/nodemcu_signed/device_secrets.h
```

The equivalent Windows commands are:

```powershell
py -m pip install -r gateway\requirements.txt
py -m gateway.device_keys --output firmware\nodemcu_signed\device_secrets.h
```

`device_secrets.h` is intentionally ignored by Git. Do not send it to anyone,
commit it, or reuse its private key on another device.

## Flash

1. Open `nodemcu_signed.ino` in Arduino IDE.
2. Select **NodeMCU 1.0 (ESP-12E Module)**.
3. Select the USB serial port for the new Type-C NodeMCU.
4. Upload the sketch.
5. Confirm that serial output reports one DS18B20 and `simulated: false`.
6. Close Serial Monitor before starting the gateway.

The gateway stores the public key locally using trust on first use. If the same
device ID later presents another key, collection stops with a security warning.
Before publishing the first batch, the anchor creates a one-time Rialo workflow
that binds the numeric device ID to the public-key fingerprint. The registration
transaction must be signed by the project's published registrar wallet. The
archive and browser verify that on-chain binding independently; the private key
never leaves the ESP8266 firmware.
