"""Number entity for flame height."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_NAME,
    DOMAIN,
    FLAME_MAX,
    FLAME_MIN,
    MODE_MANUAL_FLAME,
    MODE_OFF,
)
from .coordinator import RealFlameCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add: AddEntitiesCallback
) -> None:
    coordinator: RealFlameCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add([RealFlameFlameNumber(coordinator, entry)])


class RealFlameFlameNumber(CoordinatorEntity[RealFlameCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Flame height"
    _attr_native_min_value = FLAME_MIN
    _attr_native_max_value = FLAME_MAX
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: RealFlameCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_flame"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "Real Flame Fireplace"),
        }

    @property
    def native_value(self) -> float | None:
        st = self.coordinator.status
        if not st:
            return None
        # Prefer setting; fall back to current
        return float(st.flame_setting or st.current_flame or FLAME_MIN)

    async def async_set_native_value(self, value: float) -> None:
        st = self.coordinator.status
        temp = st.temp_setting if st else 20
        mode = MODE_MANUAL_FLAME
        if st and st.is_off:
            # Changing flame while off keeps off unless user turns on via climate/select
            mode = MODE_OFF
        await self.coordinator.async_apply_control(mode, temp, int(value))
