# intesis-custom-modbus
Custom Modbus integration for use with Intesis RTU-to-TCP in combination with Mitsubishi Heavy Industries functional modifications

On our premises are installed two large Mistubishi FDU(M) units and nine SRK units, coupled with two Hyper Inverter units. These units are wired to a Intesis Modbus RTU and TCP server. The standard modbus integration supports only a swing mode setting (https://developers.home-assistant.io/docs/core/entity/climate/#swing-modes), whereas with the Mitsubishi SRK units the swing mode 'on' setting is one of the louvre position settings. Moreove, the Mitsubishi fan mode settings (low, medium, high, powerful) where incompatible with the available Home Assistant HVAC fan modes (https://developers.home-assistant.io/docs/core/entity/climate/#fan-modes).

Thus I decided to customize the standard modbus integration to support the louvre settings through the swing mode and the applicable fan mode settings.

It further supports modbus-configured switches and binary sensors.
