# IndigoHAplugin

This is an plugin for Indigo Domotics to integrate with Home Assistant.

To get started its easy. You only need the IP, PORT and the  HA access token.
After that you can add sensor, light and relays, only pass your HA identity(ex: sensor.my_test) to the address field of your chosen device.


Something to be aware of is that the JSON part of the code is by far optimize so adding a lot of devices togheter with a low polling time may affect the performance of your mac. (50+ devices with pollingtime of 2 seconds do not affect my old Macbook air 2011).

HA websocket can be implemented to reduce the JSON message.  
