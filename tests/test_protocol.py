"""Unit tests for MWIL encode/decode using live captures."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "real_flame"


def _load(name: str, path: Path):
    """Load a module file without executing package __init__ (needs HA)."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# const has no HA deps; protocol imports .const — register both under package path
_const = _load("real_flame.const", PKG / "const.py")
sys.modules["real_flame"] = type(sys)("real_flame")
sys.modules["real_flame"].const = _const
_protocol = _load("real_flame.protocol", PKG / "protocol.py")

parse_status = _protocol.parse_status
build_control_frame = _protocol.build_control_frame
status_request = _protocol.status_request
ProtocolError = _protocol.ProtocolError
MODE_MANUAL_FLAME = _const.MODE_MANUAL_FLAME
MODE_MANUAL_TEMP = _const.MODE_MANUAL_TEMP
MODE_OFF = _const.MODE_OFF

LIVE = "MWIL11,14,01,D1B4B025,16,00,03,00,01,0E,0E,01,00,00,00,"
CAPTURES = ROOT / "captures" / "mwil10.json"


def test_status_request_bytes():
    assert status_request() == b"MWIL10"


def test_parse_live_status():
    st = parse_status(LIVE)
    assert st.temp_setting == 20
    assert st.flame_setting == 1
    assert st.opaque_field3 == "D1B4B025"
    assert st.temp_reading == 22
    assert st.state == 0
    assert st.op_state == 3
    assert st.mode_name == "external"
    assert st.current_flame == 0
    assert st.current_fan == 1
    assert st.auto_timer_slot == 14
    assert st.auto_time_day == 14
    assert st.wifi_modv_comms == 1
    assert st.led_r == 0
    assert not st.burner_active
    assert not st.is_off


def test_parse_from_capture_file():
    data = json.loads(CAPTURES.read_text())
    assert len(data) >= 1
    for item in data:
        st = parse_status(item["raw_ascii"])
        assert st.temp_setting == 20
        assert st.temp_reading == 22
        assert st.op_state == 3


def test_parse_rejects_garbage():
    with pytest.raises(ProtocolError):
        parse_status("HELLO")
    with pytest.raises(ProtocolError):
        parse_status("MWIX99,00")


def test_build_control_off():
    # Monday 2026-10-12 15:30:45 → Java day=1 → day_field = 0
    when = datetime(2026, 10, 12, 15, 30, 45)
    frame = build_control_frame(MODE_OFF, 20, 1, when=when)
    assert frame.startswith("MWIL20")
    assert frame[6:8] == "04"
    assert frame[8:10] == "14"
    assert frame[10:12] == "01"
    assert frame[12:14] == "00"
    assert frame[14:16] == "0F"
    assert frame[16:18] == "1E"
    assert frame[18:20] == "2D"
    assert frame.endswith("000000")
    assert len(frame) == 6 + 10 * 2


def test_build_control_manual_temp():
    when = datetime(2026, 10, 12, 0, 0, 0)
    frame = build_control_frame(MODE_MANUAL_TEMP, 22, 3, when=when)
    assert frame[6:8] == "00"
    assert frame[8:10] == "16"
    assert frame[10:12] == "03"


def test_build_clamps_ranges():
    when = datetime(2026, 10, 12, 0, 0, 0)
    frame = build_control_frame(MODE_MANUAL_FLAME, 99, 0, when=when)
    assert frame[8:10] == "23"  # 35 max
    assert frame[10:12] == "01"  # 1 min flame


def test_sunday_day_field_wraps():
    # Sunday 2026-10-11 → Java day 0 → (0-1)&0xFF = 0xFF
    when = datetime(2026, 10, 11, 12, 0, 0)
    frame = build_control_frame(MODE_OFF, 20, 1, when=when)
    assert frame[12:14] == "FF"


def test_is_control_ack():
    assert _protocol.is_control_ack("MWIL2,")
    assert _protocol.is_control_ack(b"MWIL2,")
    assert not _protocol.is_control_ack("MWIL20")
    assert not _protocol.is_control_ack("MWIL11,14,01")


def test_parse_status_after_local_control_clock_echo():
    # Live after OFF: field3 echoes DDHHMMSS from control
    raw = "MWIL11,14,01,030F3206,16,00,04,00,01,0E,0E,01,00,00,00,"
    st = parse_status(raw)
    assert st.op_state == 4
    assert st.is_off
    assert st.opaque_field3 == "030F3206"
    assert st.temp_setting == 20


def test_parse_on_manual_temp_live():
    raw = "MWIL11,14,01,030F320A,16,00,00,00,01,0E,0E,01,00,00,00,"
    st = parse_status(raw)
    assert st.op_state == 0
    assert st.mode_name == "manual_temperature"
    assert st.current_flame == 0  # room 22 > setpoint 20
    assert st.temp_reading == 22


def test_thursday_day_field_matches_live():
    # 2026-10-15 Thursday 15:50:06 Adelaide → Java day 4 → field 3
    when = datetime(2026, 10, 15, 15, 50, 6)
    frame = build_control_frame(MODE_OFF, 20, 1, when=when)
    assert frame == "MWIL20041401030F3206000000"


def test_burner_active_via_state_field():
    # Live ignition frame: state=01, flame=01, fan=00
    st = parse_status("MWIL11,19,01,030F3A27,16,01,00,01,00,0E,0E,01,00,00,00,")
    assert st.burner_active
    # Steady burn
    assert parse_status("MWIL11,19,01,030F3A27,16,01,00,05,03,0E,0E,01,00,00,00,").burner_active
    # state=01 alone (flame 0) still counts
    assert parse_status("MWIL11,19,01,030F3A27,16,01,00,00,03,0E,0E,01,00,00,00,").burner_active
    # Off with fan run-on resting value
    assert not parse_status("MWIL11,14,01,030F3B29,16,00,04,00,01,0E,0E,01,00,00,00,").burner_active


def test_no_fan_binary_sensor():
    src = (PKG / "binary_sensor.py").read_text()
    assert "RealFlameFan" not in src
    assert "RealFlameBurner" in src
