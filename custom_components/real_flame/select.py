"""Select entity for operating mode."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_NAME,
    DOMAIN,
    MODE_AUTO_TIMER,
    MODE_MANUAL_FLAME,
    MODE_MANUAL_TEMP,
    MODE_OFF,
)
from .coordinator import RealFlameCoordinator

# User-selectable modes (exclude opaque "external" as a write target)
SELECTABLE = {
    "off": MODE_OFF,
    "manual_temperature": MODE_MANUAL_TEMP,
    "manual_flame": MODE_MANUAL_FLAME,
    "auto": MODE_AUTO_TIMER,
}
LABEL_BY_MODE = {v: k for k, v in SELECTABLE.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add: AddEntitiesCallback
) -> None:
    coordinator: RealFlameCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add([RealFlameModeSelect(coordinator, entry)])


class RealFlameModeSelect(CoordinatorEntity[RealFlameCoordinator], SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "Mode"
    _attr_options = list(SELECTABLE.keys())

    def __init__(self, coordinator: RealFlameCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_mode"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "Real Flame Fireplace"),
        }

    @property
    def current_option(self) -> str | None:
        st = self.coordinator.status
        if not st:
            return None
        if st.op_state in LABEL_BY_MODE:
            return LABEL_BY_MODE[st.op_state]
        # Map external → show as its label but not in write list; surface via sensor
        return None  # e.g. external — see mode sensor

    async def async_select_option(self, option: str) -> None:
        if option not in SELECTABLE:
            raise ValueError(f"Unsupported mode option: {option}")
        st = self.coordinator.status
        temp = st.temp_setting if st else 20
        flame = max(1, st.flame_setting if st else 1)
        await self.coordinator.async_apply_control(SELECTABLE[option], temp, flame)
