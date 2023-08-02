# Home Assistant Agent

Home Assistant Agent is an plugin for the Indigo automation system to integrate with Home Assistant.  
This plugin allows you to create Indigo devices which act as agents for Home Assistant entities.

You need the IP address and PORT for your Home Assistant server, and an HA access token.  
The plugin uses zero-conf (aka Bonjour or mDNS) to locate Home Assistant servers on the local LAN.  If your HA instance
is not on the LAN, you can enter the IP address or DNS name and port manually.

The plugin supports the following Home Assistant device types:
 
| Home Assistant | Indigo     |
|----------------|------------|
| Climate        | Thermostat |
| Light          | Dimmer     |
| Switch         | Relay      |
| Binary Sensor  | Sensor     |
| Sensor         | Sensor     |