import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACMode, ClimateEntityFeature
)
from homeassistant.const import UnitOfTemperature
from .modbus import CustomModbus

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the custom climate platform."""
    if discovery_info is None:
        return

    modbus = hass.data['custom_modbus']
    entities = []
    try:
        entity = CustomClimate(discovery_info['name'], discovery_info, modbus)
        entities.append(entity)
    except Exception as e:
        _LOGGER.error(f"Error setting up entity: {e}")

    async_add_entities(entities)

class CustomClimate(ClimateEntity):
    def __init__(self, name, config, modbus: CustomModbus):
        self._name = name
        self._config = config
        self._modbus = modbus
        self._scale = config.get('scale', 1)
        self._precision = config.get('precision', 1)
        self._target_temp_write_registers = config.get('target_temp_write_registers', False)
        self._hvac_mode = HVACMode.OFF
        self._fan_mode = 'low'  # Default to 'low'
        self._swing_mode = 'swing'  # Default to 'swing'
        self._current_temperature = 25  # Placeholder for current temperature
        self._target_temperature = 22  # Placeholder for target temperature
        self._unique_id = config.get('unique_id', None)
        self.update()  # Initial update to fetch data from Modbus

    @property
    def name(self):
        """Return the name of the climate entity."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID for the climate entity."""
        return self._unique_id

    @property
    def swing_modes(self):
        """Return the list of available swing modes."""
        return ['Swing', 'Position 1', 'Position 2', 'Position 3', 'Position 4']

    @property
    def swing_mode(self):
        """Return the current swing mode."""
        return self._swing_mode.capitalize().replace('_', ' ')

    def set_swing_mode(self, swing_mode):
        """Set the swing mode."""
        if swing_mode.lower().replace(' ', '_') in [mode.lower().replace(' ', '_') for mode in self.swing_modes]:
            self._swing_mode = swing_mode.lower().replace(' ', '_')
            self._modbus.write_register(self._config['swing_mode_register']['address'], self._swing_mode_to_register_value(self._swing_mode))
            self.schedule_update_ha_state()

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return ['Low', 'Medium', 'High', 'Powerful']

    @property
    def fan_mode(self):
        """Return the current fan mode."""
        return self._fan_mode.capitalize()

    def set_fan_mode(self, fan_mode):
        """Set the fan mode."""
        if fan_mode.lower() in [mode.lower() for mode in self.fan_modes]:
            self._fan_mode = fan_mode.lower()
            self._modbus.write_register(self._config['fan_mode_register']['address'], self._fan_mode_to_register_value(self._fan_mode))
            self.schedule_update_ha_state()

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.FAN_ONLY, HVACMode.AUTO, HVACMode.DRY]

    @property
    def hvac_mode(self):
        """Return current operation mode."""
        return self._hvac_mode

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode in self.hvac_modes:
            self._hvac_mode = hvac_mode
            if hvac_mode == HVACMode.OFF:
                self._modbus.write_register(self._config['hvac_onoff_register'], 0)
            else:
                self._modbus.write_register(self._config['hvac_onoff_register'], 1)
                self._modbus.write_register(self._config['hvac_mode_register']['address'], self._hvac_mode_to_register_value(hvac_mode))
            self.schedule_update_ha_state()

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return round(self._current_temperature, self._precision)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return round(self._target_temperature, self._precision)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get('temperature')
        if temperature is not None:
            self._target_temperature = round(temperature, self._precision)
            register_value = int(self._target_temperature / self._scale)
            _LOGGER.debug(f"Writing temperature {self._target_temperature} (register value: {register_value}) to register {self._config['target_temp_register']}")
            success = self._modbus.write_register(self._config['target_temp_register'], register_value)
            if success:
                _LOGGER.debug(f"Successfully wrote temperature {self._target_temperature} to register {self._config['target_temp_register']}")
            else:
                _LOGGER.error(f"Failed to write temperature {self._target_temperature} to register {self._config['target_temp_register']}")
            self.schedule_update_ha_state()
        else:
            _LOGGER.debug("No temperature provided to set_temperature")

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return (
            ClimateEntityFeature.FAN_MODE | 
            ClimateEntityFeature.SWING_MODE | 
            ClimateEntityFeature.TARGET_TEMPERATURE
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "hvac_mode": self._hvac_mode,
            "fan_mode": self._fan_mode,
            "swing_mode": self._swing_mode,
            "current_temperature": self.current_temperature,
            "target_temperature": self.target_temperature,
        }

    def update(self):
        """Retrieve latest state."""
        self._modbus._client.connect()
        # Read current state from Modbus registers
        try:
            self._current_temperature = self._modbus.read_register(self._config['address']) * self._scale
            self._target_temperature = self._modbus.read_register(self._config['target_temp_register']) * self._scale
            hvac_onoff = self._modbus.read_register(self._config['hvac_onoff_register'])
            if hvac_onoff == 0:
                self._hvac_mode = HVACMode.OFF
            else:
                self._hvac_mode = self._register_value_to_hvac_mode(self._modbus.read_register(self._config['hvac_mode_register']['address']))
            self._fan_mode = self._register_value_to_fan_mode(self._modbus.read_register(self._config['fan_mode_register']['address']))
            self._swing_mode = self._register_value_to_swing_mode(self._modbus.read_register(self._config['swing_mode_register']['address']))
        except Exception as e:
            _LOGGER.error(f"Error updating state: {e}")
        self._modbus._client.close()

    def _hvac_mode_to_register_value(self, hvac_mode):
        """Convert HVAC mode to Modbus register value."""
        mapping = {
            HVACMode.COOL: self._config['hvac_mode_register']['values']['state_cool'],
            HVACMode.HEAT: self._config['hvac_mode_register']['values']['state_heat'],
            HVACMode.FAN_ONLY: self._config['hvac_mode_register']['values']['state_fan_only'],
            HVACMode.AUTO: self._config['hvac_mode_register']['values']['state_auto'],
            HVACMode.DRY: self._config['hvac_mode_register']['values']['state_dry']
        }
        return mapping.get(hvac_mode, self._config['hvac_mode_register']['values']['state_cool'])

    def _register_value_to_hvac_mode(self, value):
        """Convert Modbus register value to HVAC mode."""
        mapping = {
            self._config['hvac_mode_register']['values']['state_cool']: HVACMode.COOL,
            self._config['hvac_mode_register']['values']['state_heat']: HVACMode.HEAT,
            self._config['hvac_mode_register']['values']['state_fan_only']: HVACMode.FAN_ONLY,
            self._config['hvac_mode_register']['values']['state_auto']: HVACMode.AUTO,
            self._config['hvac_mode_register']['values']['state_dry']: HVACMode.DRY
        }
        return mapping.get(value, HVACMode.COOL)

    def _fan_mode_to_register_value(self, fan_mode):
        """Convert fan mode to Modbus register value."""
        mapping = {
            'low': self._config['fan_mode_register']['values']['low'],
            'medium': self._config['fan_mode_register']['values']['medium'],
            'high': self._config['fan_mode_register']['values']['high'],
            'powerful': self._config['fan_mode_register']['values']['powerful']
        }
        return mapping.get(fan_mode, self._config['fan_mode_register']['values']['low'])

    def _register_value_to_fan_mode(self, value):
        """Convert Modbus register value to fan mode."""
        mapping = {
            self._config['fan_mode_register']['values']['low']: 'low',
            self._config['fan_mode_register']['values']['medium']: 'medium',
            self._config['fan_mode_register']['values']['high']: 'high',
            self._config['fan_mode_register']['values']['powerful']: 'powerful'
        }
        return mapping.get(value, 'low')

    def _swing_mode_to_register_value(self, swing_mode):
        """Convert swing mode to Modbus register value."""
        mapping = {
            'swing': self._config['swing_mode_register']['values']['swing'],
            'position_1': self._config['swing_mode_register']['values']['position_1'],
            'position_2': self._config['swing_mode_register']['values']['position_2'],
            'position_3': self._config['swing_mode_register']['values']['position_3'],
            'position_4': self._config['swing_mode_register']['values']['position_4']
        }
        return mapping.get(swing_mode, self._config['swing_mode_register']['values']['swing'])

    def _register_value_to_swing_mode(self, value):
        """Convert Modbus register value to swing mode."""
        mapping = {
            self._config['swing_mode_register']['values']['swing']: 'swing',
            self._config['swing_mode_register']['values']['position_1']: 'position_1',
            self._config['swing_mode_register']['values']['position_2']: 'position_2',
            self._config['swing_mode_register']['values']['position_3']: 'position_3',
            self._config['swing_mode_register']['values']['position_4']: 'position_4'
        }
        return mapping.get(value, 'swing')
