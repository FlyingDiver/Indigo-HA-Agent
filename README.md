# Indigo-HA-Import

This is an plugin for Indigo to integrate with Home Assistant.  This plugin allows you to import
native Home Assistant devices into Indigo.  This plugin does not require any additional hardware.

You need the IP address and PORT for your Home Assistant server, and an HA access token.

The plugin supports the following Home Assistant device types:
 
| Home Assistant | Indigo     |
|----------------|------------|
| Climate        | Thermostat |
| Light          | Dimmer     |
| Switch         | Relay      |
| Binary Sensor  | Sensor     |
| Sensor         | Sensor     |