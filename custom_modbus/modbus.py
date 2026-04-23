"""Async Modbus TCP wrapper compatible with pymodbus 3.x.

This module intentionally hides the small API differences between
pymodbus 3.0 – 3.7 (``slave=``) and 3.8+ (``device_id=``) so the rest of
the integration does not need to care about it.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import pymodbus
from pymodbus.client import AsyncModbusTcpClient

_LOGGER = logging.getLogger(__name__)


def _slave_kwargs(unit_id: int) -> dict[str, int]:
    """Return the right device/slave keyword for the installed pymodbus."""
    try:
        parts = pymodbus.__version__.split(".")
        major, minor = int(parts[0]), int(parts[1])
    except Exception:  # pragma: no cover - extremely defensive
        return {"slave": unit_id}
    if (major, minor) >= (3, 8):
        return {"device_id": unit_id}
    return {"slave": unit_id}


class CustomModbus:
    """Thin async wrapper around :class:`AsyncModbusTcpClient`."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._host: str = config["host"]
        self._port: int = int(config.get("port", 502))
        self._unit_id: int = int(config.get("unit_id", 1))
        self._delay: float = float(config.get("delay", 0.0))
        self._timeout: float = float(config.get("timeout", 5))
        self._lock = asyncio.Lock()
        self._client = AsyncModbusTcpClient(
            host=self._host,
            port=self._port,
            timeout=self._timeout,
        )

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def async_connect(self) -> bool:
        """Open the TCP connection if it is not open yet."""
        if getattr(self._client, "connected", False):
            return True
        try:
            return bool(await self._client.connect())
        except Exception as err:  # pragma: no cover - network dependent
            _LOGGER.warning(
                "Could not connect to Modbus at %s:%s – %s",
                self._host,
                self._port,
                err,
            )
            return False

    async def async_close(self) -> None:
        """Close the underlying connection (best effort)."""
        try:
            close_fn = self._client.close
            result = close_fn()
            if asyncio.iscoroutine(result):
                await result
        except Exception:  # pragma: no cover - best effort
            _LOGGER.debug("Error while closing modbus client", exc_info=True)

    # ------------------------------------------------------------------
    # Register / coil helpers
    # ------------------------------------------------------------------

    async def read_register(self, address: int) -> int | None:
        """Read a single holding register.

        Returns ``None`` when the read failed so callers can decide
        whether to keep the previous state or mark the entity unavailable.
        """
        async with self._lock:
            if not await self.async_connect():
                return None
            try:
                result = await self._client.read_holding_registers(
                    address, count=1, **_slave_kwargs(self._unit_id)
                )
            except Exception as err:
                _LOGGER.warning("Exception reading register %s: %s", address, err)
                return None
            if result is None or result.isError():
                _LOGGER.debug("Error reading register %s: %s", address, result)
                return None
            try:
                return int(result.registers[0])
            except (AttributeError, IndexError, TypeError):
                return None

    async def write_register(self, address: int, value: int) -> bool:
        """Write a single holding register. Returns True on success."""
        async with self._lock:
            if not await self.async_connect():
                return False
            try:
                result = await self._client.write_register(
                    address, int(value), **_slave_kwargs(self._unit_id)
                )
            except Exception as err:
                _LOGGER.warning(
                    "Exception writing register %s=%s: %s", address, value, err
                )
                return False
            if result is None or result.isError():
                _LOGGER.warning(
                    "Error writing register %s=%s: %s", address, value, result
                )
                return False
            return True

    async def read_coil(self, address: int) -> bool | None:
        """Read a single coil."""
        async with self._lock:
            if not await self.async_connect():
                return None
            try:
                result = await self._client.read_coils(
                    address, count=1, **_slave_kwargs(self._unit_id)
                )
            except Exception as err:
                _LOGGER.warning("Exception reading coil %s: %s", address, err)
                return None
            if result is None or result.isError():
                return None
            try:
                return bool(result.bits[0])
            except (AttributeError, IndexError, TypeError):
                return None

    async def write_coil(self, address: int, value: bool) -> bool:
        """Write a single coil. Returns True on success."""
        async with self._lock:
            if not await self.async_connect():
                return False
            try:
                result = await self._client.write_coil(
                    address, bool(value), **_slave_kwargs(self._unit_id)
                )
            except Exception as err:
                _LOGGER.warning(
                    "Exception writing coil %s=%s: %s", address, value, err
                )
                return False
            if result is None or result.isError():
                return False
            return True
