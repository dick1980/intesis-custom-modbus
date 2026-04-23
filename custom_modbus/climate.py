"""Custom Modbus climate entity."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .modbus import CustomModbus

_LOGGER = logging.getLogger(__name__)

FAN_MODES = ["Low", "Medium", "High", "Powerful"]
SWING_MODES = ["Swing", "Position 1", "Position 2", "Position 3", "Position 4"]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Custom Modbus climate platform via YAML discovery."""
    if discovery_info is None:
        return

    modbus: CustomModbus = hass.data[DOMAIN]
    try:
        entity = CustomClimate(discovery_info["name"], discovery_info, modbus)
    except Exception as err:
        _LOGGER.error("Error setting up climate entity: %s", err)
        return

    async_add_entities([entity], update_before_add=True)


class CustomClimate(ClimateEntity):
    """Climate entity backed by Modbus registers."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.FAN_ONLY,
        HVACMode.AUTO,
        HVACMode.DRY,
    ]
    _attr_fan_modes = FAN_MODES
    _attr_swing_modes = SWING_MODES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    # Required since HA 2025.1 to opt out of the legacy backwards-compat shim.
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self, name: str, config: dict[str, Any], modbus: CustomModbus
    ) -> None:
        self._attr_name = name
        self._config = config
        self._modbus = modbus
        self._scale: float = float(config.get("scale", 1))
        self._precision: int = int(config.get("precision", 1))
        self._attr_unique_id = config.get("unique_id")
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_fan_mode = FAN_MODES[0]
        self._attr_swing_mode = SWING_MODES[0]
        self._attr_current_temperature: float | None = None
        self._attr_target_temperature: float | None = None

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        register_value = int(round(float(temperature) / self._scale))
        register = self._config["target_temp_register"]
        _LOGGER.debug(
            "Writing target temperature %s (register %s = %s)",
            temperature,
            register,
            register_value,
        )
        if await self._modbus.write_register(register, register_value):
            self._attr_target_temperature = round(float(temperature), self._precision)
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Failed to write target temperature %s", temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        if hvac_mode not in self._attr_hvac_modes:
            return

        if hvac_mode == HVACMode.OFF:
            ok = await self._modbus.write_register(
                self._config["hvac_onoff_register"], 0
            )
        else:
            on_ok = await self._modbus.write_register(
                self._config["hvac_onoff_register"], 1
            )
            mode_ok = await self._modbus.write_register(
                self._config["hvac_mode_register"]["address"],
                self._hvac_mode_to_register_value(hvac_mode),
            )
            ok = on_ok and mode_ok

        if ok:
            self._attr_hvac_mode = hvac_mode
            self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the climate entity on (restore last mode, fall back to COOL)."""
        target = self._attr_hvac_mode
        if target in (HVACMode.OFF, None):
            target = HVACMode.COOL
        await self.async_set_hvac_mode(target)

    async def async_turn_off(self) -> None:
        """Turn the climate entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        normalized = fan_mode.lower()
        if normalized not in {m.lower() for m in FAN_MODES}:
            return
        if await self._modbus.write_register(
            self._config["fan_mode_register"]["address"],
            self._fan_mode_to_register_value(normalized),
        ):
            self._attr_fan_mode = normalized.capitalize()
            self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        key = swing_mode.lower().replace(" ", "_")
        if key not in {m.lower().replace(" ", "_") for m in SWING_MODES}:
            return
        if await self._modbus.write_register(
            self._config["swing_mode_register"]["address"],
            self._swing_mode_to_register_value(key),
        ):
            self._attr_swing_mode = swing_mode.capitalize().replace("_", " ")
            self.async_write_ha_state()

    # ------------------------------------------------------------------
    # State polling
    # ------------------------------------------------------------------

    async def async_update(self) -> None:
        """Fetch the latest state from the Modbus device."""
        try:
            current = await self._modbus.read_register(self._config["address"])
            target = await self._modbus.read_register(
                self._config["target_temp_register"]
            )
            hvac_onoff = await self._modbus.read_register(
                self._config["hvac_onoff_register"]
            )
            hvac_raw = await self._modbus.read_register(
                self._config["hvac_mode_register"]["address"]
            )
            fan_raw = await self._modbus.read_register(
                self._config["fan_mode_register"]["address"]
            )
            swing_raw = await self._modbus.read_register(
                self._config["swing_mode_register"]["address"]
            )
        except Exception as err:
            _LOGGER.warning("Error updating climate state: %s", err)
            return

        if current is not None:
            self._attr_current_temperature = round(
                current * self._scale, self._precision
            )
        if target is not None:
            self._attr_target_temperature = round(
                target * self._scale, self._precision
            )

        if hvac_onoff == 0:
            self._attr_hvac_mode = HVACMode.OFF
        elif hvac_raw is not None:
            self._attr_hvac_mode = self._register_value_to_hvac_mode(hvac_raw)

        if fan_raw is not None:
            self._attr_fan_mode = self._register_value_to_fan_mode(fan_raw)
        if swing_raw is not None:
            self._attr_swing_mode = self._register_value_to_swing_mode(swing_raw)

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    def _hvac_mode_to_register_value(self, hvac_mode: HVACMode) -> int:
        values = self._config["hvac_mode_register"]["values"]
        mapping = {
            HVACMode.COOL: values["state_cool"],
            HVACMode.HEAT: values["state_heat"],
            HVACMode.FAN_ONLY: values["state_fan_only"],
            HVACMode.AUTO: values["state_auto"],
            HVACMode.DRY: values["state_dry"],
        }
        return mapping.get(hvac_mode, values["state_cool"])

    def _register_value_to_hvac_mode(self, value: int) -> HVACMode:
        values = self._config["hvac_mode_register"]["values"]
        mapping = {
            values["state_cool"]: HVACMode.COOL,
            values["state_heat"]: HVACMode.HEAT,
            values["state_fan_only"]: HVACMode.FAN_ONLY,
            values["state_auto"]: HVACMode.AUTO,
            values["state_dry"]: HVACMode.DRY,
        }
        return mapping.get(value, HVACMode.COOL)

    def _fan_mode_to_register_value(self, fan_mode: str) -> int:
        values = self._config["fan_mode_register"]["values"]
        mapping = {
            "low": values["low"],
            "medium": values["medium"],
            "high": values["high"],
            "powerful": values["powerful"],
        }
        return mapping.get(fan_mode, values["low"])

    def _register_value_to_fan_mode(self, value: int) -> str:
        values = self._config["fan_mode_register"]["values"]
        mapping = {
            values["low"]: "Low",
            values["medium"]: "Medium",
            values["high"]: "High",
            values["powerful"]: "Powerful",
        }
        return mapping.get(value, "Low")

    def _swing_mode_to_register_value(self, swing_mode: str) -> int:
        values = self._config["swing_mode_register"]["values"]
        mapping = {
            "swing": values["swing"],
            "position_1": values["position_1"],
            "position_2": values["position_2"],
            "position_3": values["position_3"],
            "position_4": values["position_4"],
        }
        return mapping.get(swing_mode, values["swing"])

    def _register_value_to_swing_mode(self, value: int) -> str:
        values = self._config["swing_mode_register"]["values"]
        mapping = {
            values["swing"]: "Swing",
            values["position_1"]: "Position 1",
            values["position_2"]: "Position 2",
            values["position_3"]: "Position 3",
            values["position_4"]: "Position 4",
        }
        return mapping.get(value, "Swing")
