from pymodbus.client.sync import ModbusTcpClient as ModbusClient

class CustomModbus:
    def __init__(self, config):
        self._host = config['host']
        self._port = config['port']
        self._unit_id = config['unit_id']
        self._client = ModbusClient(self._host, port=self._port)
        self._delay = config.get('delay', 0.5)
        self._timeout = config.get('timeout', 5)
        self._client.timeout = self._timeout

    def write_register(self, address, value):
        """Write a value to a Modbus register."""
        self._client.connect()
        self._client.write_register(address, value, unit=self._unit_id)
        self._client.close()

    def read_register(self, address):
        """Read a value from a Modbus register."""
        self._client.connect()
        result = self._client.read_holding_registers(address, 1, unit=self._unit_id)
        self._client.close()
        if result and hasattr(result, 'registers'):
            return result.registers[0]
        return None

    def read_coil(self, address):
        """Read a value from a Modbus coil."""
        self._client.connect()
        try:
            result = self._client.read_coils(address, 1, unit=self._unit_id)
            self._client.close()
            if result and hasattr(result, 'bits'):
                return result.bits[0]
        except Exception:
            pass
        return None

    def write_coil(self, address, value):
        """Write a value to a Modbus coil."""
        self._client.connect()
        try:
            self._client.write_coil(address, value, unit=self._unit_id)
            self._client.close()
        except Exception:
            pass
