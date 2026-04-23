"""Custom Modbus switch."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up the Custom Modbus switch platform."""
    if discovery_info is None:
        return

    modbus: CustomModbus = hass.data[DOMAIN]
    try:
        entity = CustomSwitch(discovery_info["name"], discovery_info, modbus)
    except Exception as err:
        _LOGGER.error("Error setting up switch: %s", err)
        return

    async_add_entities([entity], update_before_add=True)


class CustomSwitch(SwitchEntity):
    """Switch backed by a Modbus coil."""

    def __init__(
        self, name: str, config: dict[str, Any], modbus: CustomModbus
    ) -> None:
        self._attr_name = name
        self._config = config
        self._modbus = modbus
        self._attr_unique_id = config.get("unique_id")
        self._attr_is_on: bool | None = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if await self._modbus.write_coil(self._config["address"], True):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if await self._modbus.write_coil(self._config["address"], False):
            self._attr_is_on = False
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Retrieve latest state from the coil."""
        state = await self._modbus.read_coil(self._config["address"])
        if state is not None:
            self._attr_is_on = bool(state)
