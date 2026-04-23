"""Custom Modbus binary sensor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .modbus import CustomModbus

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Custom Modbus binary sensor platform."""
    if discovery_info is None:
        return

    modbus: CustomModbus = hass.data[DOMAIN]
    try:
        entity = CustomBinarySensor(discovery_info["name"], discovery_info, modbus)
    except Exception as err:
        _LOGGER.error("Error setting up binary sensor: %s", err)
        return

    async_add_entities([entity], update_before_add=True)


class CustomBinarySensor(BinarySensorEntity):
    """Binary sensor backed by a Modbus coil."""

    def __init__(
        self, name: str, config: dict[str, Any], modbus: CustomModbus
    ) -> None:
        self._attr_name = name
        self._config = config
        self._modbus = modbus
        self._attr_unique_id = config.get("unique_id")
        self._attr_is_on: bool | None = None

    async def async_update(self) -> None:
        """Retrieve latest state from the coil."""
        state = await self._modbus.read_coil(self._config["address"])
        if state is not None:
            self._attr_is_on = bool(state)
