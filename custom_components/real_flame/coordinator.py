"""Data update coordinator for Real Flame."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import RealFlameClient
from .const import (
    CONF_AUTO_OFF_HOURS,
    CONF_BLOCK_TURN_ON,
    CONF_POLL_INTERVAL,
    DEFAULT_AUTO_OFF_HOURS,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MODE_OFF,
)
from .protocol import FireplaceStatus

_LOGGER = logging.getLogger(__name__)


class RealFlameCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll MWIL10 and track safety auto-off."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: RealFlameClient,
    ) -> None:
        self.client = client
        self.entry = entry
        self._last_non_off_at: datetime | None = None
        poll = entry.options.get(
            CONF_POLL_INTERVAL,
            entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=int(poll)),
            config_entry=entry,
        )

    @property
    def block_turn_on(self) -> bool:
        return bool(
            self.entry.options.get(
                CONF_BLOCK_TURN_ON, self.entry.data.get(CONF_BLOCK_TURN_ON, False)
            )
        )

    @property
    def auto_off_hours(self) -> float:
        return float(
            self.entry.options.get(
                CONF_AUTO_OFF_HOURS,
                self.entry.data.get(CONF_AUTO_OFF_HOURS, DEFAULT_AUTO_OFF_HOURS),
            )
        )

    @property
    def status(self) -> FireplaceStatus | None:
        if not self.data:
            return None
        return self.data.get("status")

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            status = await self.client.async_get_status()
        except Exception as err:
            raise UpdateFailed(str(err)) from err

        now = datetime.now().astimezone()
        if status.is_off:
            self._last_non_off_at = None
        elif self._last_non_off_at is None:
            self._last_non_off_at = now

        auto_off_triggered = False
        hours = self.auto_off_hours
        if (
            hours > 0
            and self._last_non_off_at is not None
            and not status.is_off
            and (now - self._last_non_off_at) >= timedelta(hours=hours)
        ):
            _LOGGER.warning(
                "Auto-off: fireplace on for >= %s h — sending MODE_OFF", hours
            )
            try:
                await self.client.async_send_control(
                    MODE_OFF,
                    status.temp_setting,
                    max(1, status.flame_setting),
                )
                auto_off_triggered = True
                self._last_non_off_at = None
                status = await self.client.async_get_status()
            except Exception as err:
                _LOGGER.error("Auto-off control failed: %s", err)

        return {
            "status": status,
            "last_non_off_at": self._last_non_off_at,
            "auto_off_triggered": auto_off_triggered,
            "block_turn_on": self.block_turn_on,
        }

    async def async_apply_control(
        self, mode: int, temperature: int, flame: int
    ) -> None:
        """Send control respecting block_turn_on; refresh afterwards."""
        if mode != MODE_OFF and self.block_turn_on:
            raise PermissionError("Turn-on blocked by integration safety option")
        status = await self.client.async_send_control(mode, temperature, flame)
        if mode == MODE_OFF:
            self._last_non_off_at = None
        else:
            self._last_non_off_at = datetime.now().astimezone()
        if status is not None:
            self.async_set_updated_data(
                {
                    "status": status,
                    "last_non_off_at": self._last_non_off_at,
                    "auto_off_triggered": False,
                    "block_turn_on": self.block_turn_on,
                }
            )
        else:
            await self.async_request_refresh()
