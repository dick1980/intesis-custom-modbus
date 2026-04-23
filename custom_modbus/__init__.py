"""The custom_modbus component."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .modbus import CustomModbus

_LOGGER = logging.getLogger(__name__)

# Mapping of HA platform name -> YAML key that contains the per-entity config.
_PLATFORMS: dict[str, str] = {
    "climate": "climates",
    "binary_sensor": "binary_sensors",
    "switch": "switches",
}

_HUB_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=502): cv.port,
        vol.Required("unit_id"): cv.positive_int,
        vol.Optional("delay", default=0): vol.Coerce(float),
        vol.Optional("timeout", default=5): vol.Coerce(float),
        vol.Optional("climates", default=list): list,
        vol.Optional("binary_sensors", default=list): list,
        vol.Optional("switches", default=list): list,
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [_HUB_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Custom Modbus component from YAML."""
    if DOMAIN not in config:
        return True

    root_cfg = config[DOMAIN][0]
    modbus = CustomModbus(root_cfg)
    hass.data[DOMAIN] = modbus

    # Kick off the first connect in the background so YAML setup is not blocked
    # when the Modbus device is (temporarily) unreachable at boot time.
    hass.async_create_task(modbus.async_connect())

    tasks: list[asyncio.Task] = []
    for platform, platform_config_key in _PLATFORMS.items():
        for entry in root_cfg.get(platform_config_key, []):
            tasks.append(
                hass.async_create_task(
                    discovery.async_load_platform(
                        hass, platform, DOMAIN, entry, config
                    )
                )
            )

    if tasks:
        await asyncio.gather(*tasks)

    async def _async_shutdown(_event: Any) -> None:
        await modbus.async_close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_shutdown)

    return True
