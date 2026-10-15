"""Encode/decode Millec Real Flame MWIL ASCII frames (from APK)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .const import (
    CMD_CONTROL_PREFIX,
    CMD_STATUS,
    FLAME_MAX,
    FLAME_MIN,
    MODE_LABELS,
    MODE_OFF,
    TEMP_MAX,
    TEMP_MIN,
)


@dataclass(frozen=True)
class FireplaceStatus:
    """Parsed MWIL1x status response."""

    raw: str
    temp_setting: int
    flame_setting: int
    opaque_field3: str
    temp_reading: int
    state: int
    op_state: int
    current_flame: int
    current_fan: int
    auto_timer_slot: int
    auto_time_day: int
    wifi_modv_comms: int
    led_r: int = 0
    led_g: int = 0
    led_b: int = 0

    @property
    def mode_name(self) -> str:
        return MODE_LABELS.get(self.op_state, f"unknown_{self.op_state}")

    @property
    def is_off(self) -> bool:
        return self.op_state == MODE_OFF

    @property
    def burner_active(self) -> bool:
        return self.current_flame > 0 or self.state == 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "temp_setting": self.temp_setting,
            "flame_setting": self.flame_setting,
            "opaque_field3": self.opaque_field3,
            "temp_reading": self.temp_reading,
            "state": self.state,
            "op_state": self.op_state,
            "mode_name": self.mode_name,
            "current_flame": self.current_flame,
            "current_fan": self.current_fan,
            "auto_timer_slot": self.auto_timer_slot,
            "auto_time_day": self.auto_time_day,
            "wifi_modv_comms": self.wifi_modv_comms,
            "led_r": self.led_r,
            "led_g": self.led_g,
            "led_b": self.led_b,
            "burner_active": self.burner_active,
            "is_off": self.is_off,
        }


class ProtocolError(ValueError):
    """Invalid MWIL frame."""


def is_control_ack(payload: str | bytes) -> bool:
    """True if payload is the live MWIL20 ACK (`MWIL2,`)."""
    if isinstance(payload, bytes):
        text = payload.decode("ascii", errors="ignore").strip()
    else:
        text = payload.strip()
    return text.startswith("MWIL2") and not text.startswith("MWIL20")


def status_request() -> bytes:
    """Return ASCII bytes for MWIL10 status poll."""
    return CMD_STATUS.encode("ascii")


def build_control_frame(
    mode: int,
    temperature: int,
    flame: int,
    *,
    when: datetime | None = None,
    led_r: int = 0,
    led_g: int = 0,
    led_b: int = 0,
) -> str:
    """Build MWIL20 control frame (hex fields, no separators).

    Matches ModulatingValve.GetLocalControlSendCommandRequest().
    """
    if mode not in MODE_LABELS:
        raise ProtocolError(f"invalid mode {mode}")
    temperature = max(TEMP_MIN, min(TEMP_MAX, int(temperature)))
    flame = max(FLAME_MIN, min(FLAME_MAX, int(flame)))
    led_r = max(0, min(255, int(led_r)))
    led_g = max(0, min(255, int(led_g)))
    led_b = max(0, min(255, int(led_b)))

    when = when or datetime.now()
    # Java Date.getDay(): 0=Sunday … 6=Saturday; APK sends (getDay() - 1) as byte
    java_day = (when.weekday() + 1) % 7  # convert Mon=0… to Java Sun=0…
    day_field = (java_day - 1) & 0xFF

    parts = [
        CMD_CONTROL_PREFIX,
        f"{mode & 0xFF:02X}",
        f"{temperature & 0xFF:02X}",
        f"{flame & 0xFF:02X}",
        f"{day_field:02X}",
        f"{when.hour & 0xFF:02X}",
        f"{when.minute & 0xFF:02X}",
        f"{when.second & 0xFF:02X}",
        f"{led_r & 0xFF:02X}",
        f"{led_g & 0xFF:02X}",
        f"{led_b & 0xFF:02X}",
    ]
    return "".join(parts)


def parse_status(payload: str | bytes) -> FireplaceStatus:
    """Parse MWIL1x CSV status per APK processRXTCPData()."""
    if isinstance(payload, bytes):
        text = payload.decode("ascii", errors="ignore").strip()
    else:
        text = payload.strip()

    if not text.startswith("MWI"):
        raise ProtocolError(f"bad prefix: {text!r}")
    if len(text) < 5 or text[3:5] != "L1":
        raise ProtocolError(f"not a status frame: {text!r}")

    parts = text.split(",")
    if len(parts) < 12:
        raise ProtocolError(f"status too short ({len(parts)} fields): {text!r}")

    def hx(i: int) -> int:
        return int(parts[i].strip(), 16)

    led_r = led_g = led_b = 0
    if len(parts) >= 15 and parts[12].strip() != "":
        # APK multiplies by 2 when loading into settings
        led_r = hx(12) * 2
        led_g = hx(13) * 2
        led_b = hx(14) * 2

    return FireplaceStatus(
        raw=text,
        temp_setting=hx(1),
        flame_setting=hx(2),
        opaque_field3=parts[3].strip(),
        temp_reading=hx(4),
        state=hx(5),
        op_state=hx(6),
        current_flame=hx(7),
        current_fan=hx(8),
        auto_timer_slot=hx(9),
        auto_time_day=hx(10),
        wifi_modv_comms=hx(11),
        led_r=led_r,
        led_g=led_g,
        led_b=led_b,
    )
