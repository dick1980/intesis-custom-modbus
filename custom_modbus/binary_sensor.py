from homeassistant.components.binary_sensor import BinarySensorEntity
from .modbus import CustomModbus

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the custom binary sensor platform."""
    if discovery_info is None:
        return

    modbus = hass.data['custom_modbus']
    entities = []
    try:
        entity = CustomBinarySensor(discovery_info['name'], discovery_info, modbus)
        entities.append(entity)
    except Exception as e:
        return

    async_add_entities(entities)

class CustomBinarySensor(BinarySensorEntity):
    def __init__(self, name, config, modbus: CustomModbus):
        self._name = name
        self._config = config
        self._modbus = modbus
        self._state = None
        self._unique_id = config.get('unique_id', None)
        self.update()

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID for the binary sensor."""
        return self._unique_id

    def update(self):
        """Retrieve latest state."""
        try:
            self._state = self._modbus.read_coil(self._config['address'])
        except Exception:
            pass
