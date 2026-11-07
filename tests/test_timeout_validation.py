"""Coverage for Zigbee Pulse timeout validation boundaries."""
import importlib.util
from pathlib import Path
import unittest


_CONST_PATH = Path(__file__).parents[1] / "custom_components" / "zigbee_pulse" / "const.py"
_SPEC = importlib.util.spec_from_file_location("zigbee_pulse_const", _CONST_PATH)
_CONST = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_CONST)


class TimeoutValidationTests(unittest.TestCase):
    def test_global_timeout_boundaries(self):
        self.assertEqual(_CONST.validate_minutes(1, minimum=1, maximum=10080), 1)
        self.assertEqual(_CONST.validate_minutes("10080", minimum=1, maximum=10080), 10080)

    def test_startup_grace_allows_zero_and_maximum(self):
        self.assertEqual(_CONST.validate_minutes(0, minimum=0, maximum=120), 0)
        self.assertEqual(_CONST.validate_minutes(120, minimum=0, maximum=120), 120)

    def test_device_zero_is_the_inherit_global_value(self):
        self.assertEqual(_CONST.validate_minutes(0, minimum=0, maximum=10080), 0)

    def test_blank_and_non_numeric_values_are_rejected(self):
        for value in ("", "   ", "abc", "1.5", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _CONST.validate_minutes(value, minimum=0, maximum=10080)

    def test_out_of_range_values_are_rejected(self):
        for value, minimum, maximum in ((0, 1, 10080), (-1, 0, 10080), (10081, 0, 10080)):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _CONST.validate_minutes(value, minimum=minimum, maximum=maximum)

    def test_booleans_are_not_minute_values(self):
        with self.assertRaises(ValueError):
            _CONST.validate_minutes(True, minimum=0, maximum=10080)


if __name__ == "__main__":
    unittest.main()
