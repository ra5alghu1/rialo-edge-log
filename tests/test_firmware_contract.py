from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FirmwareContractTests(unittest.TestCase):
    def test_physical_ds18b20_is_signed_on_d4(self) -> None:
        firmware = (
            ROOT / "firmware" / "nodemcu_signed" / "nodemcu_signed.ino"
        ).read_text(encoding="utf-8")
        self.assertIn("constexpr uint8_t kOneWirePin = D4", firmware)
        self.assertIn("DallasTemperature", firmware)
        self.assertIn('"\\\"simulated\\\":false', firmware)
        self.assertIn('"3|%s|%lu|%lu|%ld|0|', firmware)

    def test_builtin_gpio2_led_does_not_drive_the_one_wire_bus(self) -> None:
        firmware = (
            ROOT / "firmware" / "nodemcu_signed" / "nodemcu_signed.ino"
        ).read_text(encoding="utf-8")
        self.assertNotIn("digitalWrite(LED_BUILTIN", firmware)
        self.assertNotIn("pinMode(LED_BUILTIN", firmware)


if __name__ == "__main__":
    unittest.main()
