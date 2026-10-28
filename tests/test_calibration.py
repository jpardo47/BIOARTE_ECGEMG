import json

import numpy as np
import pytest

from app.data_recorder import load_calibration, save_calibration
from app.models import Calibration


@pytest.mark.parametrize("source", ["env", "rms", "envelope"])
def test_normalization_is_clipped_to_unit_range(source):
    cal = Calibration(source, 0.1, 0.5, False, "now")
    np.testing.assert_allclose(cal.normalize([-0.1, 0.1, 0.3, 0.5, 1]), [0, 0, 0.5, 1, 1], atol=1e-7)


def test_invalid_calibration_rejected():
    for cal in (Calibration("unknown", 0, 1), Calibration("env", 2, 1), Calibration("env", 0, float("nan"))):
        with pytest.raises(ValueError):
            cal.validate()


def test_save_load_and_simulated_flag(tmp_path):
    path = tmp_path / "demo.json"
    original = Calibration("envelope", 0.03, 0.7, True, "2026-02-03T04:05:06Z")
    save_calibration(original, path)
    assert load_calibration(path) == original
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["simulated"] is True
