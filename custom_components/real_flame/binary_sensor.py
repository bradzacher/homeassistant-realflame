"""Binary sensors for burner / fan."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, DOMAIN
from .coordinator import RealFlameCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add: AddEntitiesCallback
) -> None:
    coordinator: RealFlameCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add(
        [
            RealFlameBurner(coordinator, entry),
        ]
    )


class _Base(CoordinatorEntity[RealFlameCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: RealFlameCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "Real Flame Fireplace"),
        }


class RealFlameBurner(_Base):
    _attr_name = "Burner"
    _attr_device_class = BinarySensorDeviceClass.HEAT

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "burner")

    @property
    def is_on(self) -> bool | None:
        st = self.coordinator.status
        return st.burner_active if st else None

