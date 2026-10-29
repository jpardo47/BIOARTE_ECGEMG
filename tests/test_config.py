import json
import pytest
from app.config import AppConfig


def test_config_roundtrip(tmp_path):
    config = AppConfig()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config.to_dict()), encoding="utf-8")
    loaded = AppConfig.load(path)
    assert loaded.adc_reference_voltage == 5.0
    assert loaded.filters.ecg_band == [0.5, 40.0]
    assert loaded.baudrate == 230400


@pytest.mark.parametrize(
    "change",
    [
        {"sample_rate": 0},
        {"adc_reference_voltage": float("nan")},
        {"block_size": 1.5},
        {"window_s": 20},
        {"volume_min": 0.9, "volume_max": 0.1},
        {"normalization_source": "bad"},
        {"pentatonic": ()},
    ],
)
def test_invalid_configuration(change):
    with pytest.raises(ValueError):
        AppConfig(**change)
