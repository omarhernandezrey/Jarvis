import array
import math

import pytest

from hud_pro.audio import level_from_float, level_from_pcm16, rms_to_level


def _sine_pcm16(amplitude: float, n: int = 1024) -> bytes:
    a = array.array("h", (int(amplitude * 32767 * math.sin(i * 0.1)) for i in range(n)))
    return a.tobytes()


def test_rms_to_level_bounds():
    assert rms_to_level(0) == 0.0
    assert rms_to_level(-1) == 0.0
    assert rms_to_level(float("nan")) == 0.0
    assert rms_to_level("x") == 0.0
    assert rms_to_level(1.0) == 1.0
    assert rms_to_level(5.0) == 1.0
    assert 0.0 < rms_to_level(0.05) < 1.0


def test_rms_to_level_rejects_bad_floor():
    with pytest.raises(ValueError):
        rms_to_level(0.5, floor_db=0)


def test_pcm16_monotonic_with_loudness():
    quiet = level_from_pcm16(_sine_pcm16(0.01))
    loud = level_from_pcm16(_sine_pcm16(0.5))
    assert 0.0 <= quiet < loud <= 1.0
    assert level_from_pcm16(b"") == 0.0
    assert level_from_pcm16(b"\x01") == 0.0  # byte suelto ignorado


def test_float_samples():
    assert level_from_float([]) == 0.0
    assert level_from_float([0.0] * 100) == 0.0
    assert level_from_float([0.5, -0.5] * 100) > level_from_float([0.01, -0.01] * 100)
