"""Climate entity — temperature / off modes."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_NAME,
    DOMAIN,
    MODE_MANUAL_TEMP,
    MODE_OFF,
    TEMP_MAX,
    TEMP_MIN,
)
from .coordinator import RealFlameCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add: AddEntitiesCallback
) -> None:
    coordinator: RealFlameCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add([RealFlameClimate(coordinator, entry)])


class RealFlameClimate(CoordinatorEntity[RealFlameCoordinator], ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_min_temp = TEMP_MIN
    _attr_max_temp = TEMP_MAX
    _attr_target_temperature_step = 1.0

    @property
    def extra_state_attributes(self) -> dict[str, int] | None:
        st = self.coordinator.status
        return {"fan_level": st.current_fan} if st else None

    def __init__(self, coordinator: RealFlameCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "Real Flame Fireplace"),
            "manufacturer": "Real Flame / Millec",
            "model": "Element Mk2 (WGM110)",
        }

    @property
    def current_temperature(self) -> float | None:
        st = self.coordinator.status
        return float(st.temp_reading) if st else None

    @property
    def target_temperature(self) -> float | None:
        st = self.coordinator.status
        return float(st.temp_setting) if st else None

    @property
    def hvac_mode(self) -> HVACMode:
        st = self.coordinator.status
        if not st or st.is_off:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        st = self.coordinator.status
        if not st or st.is_off:
            return HVACAction.OFF
        if st.burner_active:
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        st = self.coordinator.status
        flame = st.flame_setting if st else 1
        mode = MODE_OFF if (st and st.is_off) else MODE_MANUAL_TEMP
        if mode == MODE_OFF:
            mode = MODE_MANUAL_TEMP
        await self.coordinator.async_apply_control(mode, int(temp), max(1, flame))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        st = self.coordinator.status
        temp = st.temp_setting if st else 20
        flame = max(1, st.flame_setting if st else 1)
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_apply_control(MODE_OFF, temp, flame)
        elif hvac_mode == HVACMode.HEAT:
            await self.coordinator.async_apply_control(MODE_MANUAL_TEMP, temp, flame)
