"""Sensors for Real Flame status."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, DOMAIN, MODE_LABELS
from .coordinator import RealFlameCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add: AddEntitiesCallback
) -> None:
    coordinator: RealFlameCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add(
        [
            RealFlameRoomTemp(coordinator, entry),
            RealFlameModeSensor(coordinator, entry),
            RealFlameOpState(coordinator, entry),
            RealFlameComms(coordinator, entry),
            RealFlameRaw(coordinator, entry),
        ]
    )


class _Base(CoordinatorEntity[RealFlameCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: RealFlameCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "Real Flame Fireplace"),
        }


class RealFlameRoomTemp(_Base):
    _attr_name = "Room temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "room_temp")

    @property
    def native_value(self):
        st = self.coordinator.status
        return st.temp_reading if st else None


class RealFlameModeSensor(_Base):
    _attr_name = "Operating mode"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "mode_name")

    @property
    def native_value(self):
        st = self.coordinator.status
        return st.mode_name if st else None


class RealFlameOpState(_Base):
    _attr_name = "Operating mode code"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "op_state")

    @property
    def native_value(self):
        st = self.coordinator.status
        return st.op_state if st else None


class RealFlameComms(_Base):
    _attr_name = "Module to valve status"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "wifi_modv")

    @property
    def native_value(self):
        st = self.coordinator.status
        return st.wifi_modv_comms if st else None


class RealFlameRaw(_Base):
    _attr_name = "Last status frame"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "raw")

    @property
    def native_value(self):
        st = self.coordinator.status
        return st.raw if st else None
