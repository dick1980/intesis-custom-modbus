from homeassistant.components.switch import SwitchEntity
from .modbus import CustomModbus

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the custom switch platform."""
    if discovery_info is None:
        return

    modbus = hass.data['custom_modbus']
    entities = []
    try:
        entity = CustomSwitch(discovery_info['name'], discovery_info, modbus)
        entities.append(entity)
    except Exception as e:
        return

    async_add_entities(entities)

class CustomSwitch(SwitchEntity):
    def __init__(self, name, config, modbus: CustomModbus):
        self._name = name
        self._config = config
        self._modbus = modbus
        self._state = None
        self._unique_id = config.get('unique_id', None)
        self.update()

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID for the switch."""
        return self._unique_id

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        try:
            self._modbus.write_coil(self._config['address'], True)
            self._state = True
            self.schedule_update_ha_state()
        except Exception:
            pass

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        try:
            self._modbus.write_coil(self._config['address'], False)
            self._state = False
            self.schedule_update_ha_state()
        except Exception:
            pass

    def update(self):
        """Retrieve latest state."""
        try:
            self._state = self._modbus.read_coil(self._config['address'])
        except Exception:
            pass
