"""The custom_modbus component."""
import asyncio
from homeassistant.helpers import discovery
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .modbus import CustomModbus

DOMAIN = 'custom_modbus'

async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up the Custom Modbus component."""
    if DOMAIN not in config:
        return True

    # Set up Modbus connection
    hass.data[DOMAIN] = CustomModbus(config[DOMAIN][0])

    tasks = []
    platforms = {
        'climate': 'climates',
        'binary_sensor': 'binary_sensors',
        'switch': 'switches'
    }

    for platform, platform_config_key in platforms.items():
        platform_config = config[DOMAIN][0].get(platform_config_key, [])
        for entry in platform_config:
            task = discovery.async_load_platform(
                hass, platform, DOMAIN, entry, config
            )
            tasks.append(task)

    if tasks:
        await asyncio.gather(*tasks)

    return True
