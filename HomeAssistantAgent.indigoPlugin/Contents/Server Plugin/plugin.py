#! /usr/bin/env python
# -*- coding: utf-8 -*-

import indigo
import requests
import logging
import json
import threading

try:
    import websocket
    from zeroconf import IPVersion, ServiceBrowser, ServiceStateChange, Zeroconf
except ImportError:
    raise ImportError("'Required Python libraries missing.  Run 'pip3 install websocket-client zeroconf' in Terminal window, then reload plugin.")


################################################################################
HVAC_MODE_ENUM_TO_STR_MAP = {
    indigo.kHvacMode.Cool: "cool",
    indigo.kHvacMode.Heat: "heat",
    indigo.kHvacMode.HeatCool: "heat_cool",
    indigo.kHvacMode.Off: "off",
    indigo.kHvacMode.ProgramHeat: "heat",
    indigo.kHvacMode.ProgramCool: "cool",
    indigo.kHvacMode.ProgramHeatCool: "heat_cool"
}

HVAC_MODE_STR_TO_ENUM_MAP = {
    'heat': indigo.kHvacMode.Heat,
    'cool': indigo.kHvacMode.Cool,
    'heat_cool': indigo.kHvacMode.HeatCool,
    'auto': indigo.kHvacMode.HeatCool,
    'dry': indigo.kHvacMode.Off,
    'fan_only': indigo.kHvacMode.Off,
    'off': indigo.kHvacMode.Off
}

FAN_MODE_ENUM_TO_STR_MAP = {
    indigo.kFanMode.AlwaysOn: "always on",
    indigo.kFanMode.Auto: "auto"
}

FAN_MODE_STR_TO_ENUM_MAP = {
    'auto': indigo.kFanMode.Auto,
    'on': indigo.kFanMode.AlwaysOn
}

################################################################################

class Plugin(indigo.PluginBase):

    ########################################
    # Main Plugin Functions
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)

        self.websocket_thread = None
        self.logLevel = None
        self.ha_token = None
        self.server_port = None
        self.server_address = None
        self.ws = None
        self.sent_messages = {}
        self.found_ha_servers = {}
        self.entity_devices = {}
        self.last_sent_id = 0
        self.ha_entity_map = {}

        self.updatePrefs(pluginPrefs)

    def updatePrefs(self, pluginPrefs):
        self.server_address = pluginPrefs.get('address', 'localhost')
        self.server_port = (pluginPrefs.get('port', '8123'))
        self.ha_token = pluginPrefs.get('haToken', '')
        self.logLevel = int(pluginPrefs.get("logLevel", logging.INFO))
        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.debug(f"logLevel = {self.logLevel}")

    ########################################
    def startup(self):
        self.logger.debug("startup called")
        indigo.devices.subscribeToChanges()

        zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        services = ["_home-assistant._tcp.local."]
        browser = ServiceBrowser(zeroconf, services, handlers=[self.on_service_state_change])

        # start up the websocket receiver thread
        ws_url = f"ws://{self.server_address}:{self.server_port}/api/websocket"
        self.websocket_thread = threading.Thread(target=self.ws_client, args=(ws_url,)).start()

    def on_service_state_change(self, zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        self.logger.debug(f"Service {name} of type {service_type} state changed: {state_change}")
        info = zeroconf.get_service_info(service_type, name)
        self.logger.debug(f"Service info: {info}")
        ip_address = ".".join([f"{x}" for x in info.addresses[0]])  # address as string (xx.xx.xx.xx)
        self.logger.debug(f"Service address: {ip_address}:{info.port}")

        if state_change in [ServiceStateChange.Added, ServiceStateChange.Updated]:
            info = zeroconf.get_service_info(service_type, name)
            if name not in self.found_ha_servers:
                self.found_ha_servers[name] = {'ip_address': ip_address, 'port': info.port}

        elif state_change is ServiceStateChange.Removed:
            info = zeroconf.get_service_info(service_type, name)
            if name in self.found_ha_servers:
                del self.found_ha_servers[name]

        self.logger.debug(f"Found HA Servers: {self.found_ha_servers}")

    def shutdown(self):
        self.logger.debug("shutdown called")

    ########################################

    def deviceStartComm(self, device):
        self.logger.info(f"{device.name}: Starting device with address: {device.address}")
        device.stateListOrDisplayStateIdChanged()
        self.entity_devices[device.address] = device.id
        parts = device.address.split('.')
        try:
            entity = self.ha_entity_map[parts[0]][parts[1]]
        except Exception as err:
            self.logger.debug(f"{device.name}: {device.address} not in ha_entity_map[{parts[0]}][{parts[1]}]")
            return

        # check the attributes for the device and update the Indigo device definition
        new_props = device.pluginProps
        if device.deviceTypeId == "HAclimate":
            if entity['attributes'].get('current_temperature', None):
                new_props["NumTemperatureInputs"] = 1
            else:
                new_props["NumTemperatureInputs"] = 0

            if entity['attributes'].get('current_humidity', None):
                new_props["NumHumidityInputs"] = 1
            else:
                new_props["NumHumidityInputs"] = 0

            if entity['attributes'].get('fan_mode', None):
                new_props["SupportsHvacFanMode"] = True
            else:
                new_props["SupportsHvacFanMode"] = False

        elif device.deviceTypeId == "HAdimmerType":
            pass

        elif device.deviceTypeId == "HAswitchType":
            pass

        elif device.deviceTypeId == "HAbinarySensorType":
            pass

        elif device.deviceTypeId == "HAsensor":
            pass

        device.replacePluginPropsOnServer(new_props)
        self.update_device(entity['entity_id'], entity, force_update=True)  # force update of Indigo device

    def deviceStopComm(self, device):
        self.logger.info(f"{device.name}: Stopping device with address: {device.address}")
        del self.entity_devices[device.address]

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self.updatePrefs(valuesDict)

    def found_server_list(self, filter=None, valuesDict=None, typeId=0, targetId=0):
        self.logger.debug(f"found_server_list: filter = {filter}, typeId = {typeId}, targetId = {targetId}, valuesDict = {valuesDict}")
        retList = []
        for name, data in self.found_ha_servers.items():
            retList.append((name, f"{name} ({data['ip_address']}:{data['port']})"))
        self.logger.debug(f"found_station_list: retList = {retList}")
        return retList

    def menuChangedConfig(self, valuesDict):
        self.logger.debug(f"menuChanged: valuesDict = {valuesDict}")
        data = self.found_ha_servers.get(valuesDict['found_list'], None)
        valuesDict['address'] = data['ip_address']
        valuesDict['port'] = data['port']
        return valuesDict

    def get_entity_list(self, filter="", valuesDict=None, typeId="", targetId=0):
        retList = []
        for entity_name, entity in self.ha_entity_map[filter].items():
            retList.append((entity['entity_id'], entity_name))
        retList.sort(key=lambda tup: tup[1])
        self.logger.debug(f"get_entity_list for filter '{filter}': retList = {retList}")
        return retList

    def menuChanged(self, valuesDict, typeId, devId):
        self.logger.debug(f"menuChanged: typeId = {typeId}, devId = {devId}, valuesDict = {valuesDict}")
        return valuesDict

    def update_device(self, entity_id, entity, force_update=False):

        # save the entity state info in the entity map
        parts = entity['entity_id'].split('.')
        if parts[0] not in self.ha_entity_map:
            self.ha_entity_map[parts[0]] = {}
        self.ha_entity_map[parts[0]][parts[1]] = entity

        # find the matching Indigo device, update if we have one

        device_id = self.entity_devices.get(entity_id, None)
        if not device_id:
            self.logger.threaddebug(f"Ignoring update from entity `{entity_id}`, no matching Indigo device found")
            return

        device = indigo.devices[device_id]

        if entity["last_updated"] == device.states['lastUpdated'] and not force_update:
            self.logger.threaddebug(f"Device {device.name} already up to date")
            return

        attributes = entity.get("attributes", None)
        if not attributes:
            self.logger.error(f"Device {device.name} no attributes")
            return

        self.logger.debug(f"Updating device {device.name} with {entity}")
        if device.deviceTypeId == "HAclimate":

            if entity["last_updated"] != device.states['lastUpdated']:
                update_list = [
                    {'key': "hvacOperationMode", 'value': HVAC_MODE_STR_TO_ENUM_MAP[entity["state"].lower()]},
                    {'key': "lastUpdated", 'value': entity["last_updated"]},
                ]
                # HA setpoints are wonky
                if attributes.get("preset_mode", None):
                    update_list.append({'key': "preset_mode", 'value': attributes["preset_mode"]})
                else:
                    update_list.append({'key': "preset_mode", 'value': ""})

                if attributes.get("current_temperature", None):
                    update_list.append({'key': "hvacFanIsOn", 'value': attributes["fan_mode"] == "on"})

                if attributes.get("current_temperature", None):
                    update_list.append({'key': "temperatureInput1", 'value': attributes["current_temperature"], 'uiValue': f"{attributes['current_temperature']}\u00b0F"})

                if attributes.get("current_humidity", None):
                    update_list.append({'key': "humidityInput1", 'value': attributes["current_humidity"]})

                if attributes.get("fan_mode", None):
                    update_list.append({'key': "hvacFanMode", 'value': FAN_MODE_STR_TO_ENUM_MAP[attributes["fan_mode"].lower()]})

                if attributes.get("temperature", None):
                    update_list.append({'key': "setpointHeat", 'value': attributes["temperature"]})
                    update_list.append({'key': "setpointCool", 'value': attributes["temperature"]})
                elif attributes.get('target_temp_high', None) and attributes.get('target_temp_low', None):
                        update_list.append({'key': "setpointHeat", 'value': attributes["target_temp_low"]})
                        update_list.append({'key': "setpointCool", 'value': attributes["target_temp_high"]})
                try:
                    self.logger.threaddebug(f"do_update: update_list: {update_list}")
                    device.updateStatesOnServer(update_list)
                except Exception as e:
                    self.logger.error(f"{device.name}: failed to update states: {e}")

        elif device.deviceTypeId == "HAbinarySensorType":
            if entity["last_updated"] != device.states['lastUpdated']:
                isOff = entity["state"] == 'off'
                if isOff:
                    device.updateStateOnServer("onOffState", value=False)
                else:
                    device.updateStateOnServer("onOffState", value=True)
                device.updateStateOnServer("lastUpdated", value=entity["last_updated"])
                if attributes.get('device_class', None) == 'occupancy':
                    device.updateStateImageOnServer(indigo.kStateImageSel.MotionSensor if isOff else indigo.kStateImageSel.MotionSensorTripped)
                elif attributes.get('device_class', None) == 'problem':
                    device.updateStateImageOnServer(indigo.kStateImageSel.SensorOn if isOff else indigo.kStateImageSel.SensorTripped)
                else:
                    device.updateStateImageOnServer(indigo.kStateImageSel.NoImage)

        elif device.deviceTypeId == "HAsensor":
            if entity["last_updated"] != device.states['lastUpdated']:
                units = attributes.get("unit_of_measurement", "")
                device.updateStateOnServer("sensorValue", value=entity["state"], uiValue=f"{entity['state']}{units}")
                device.updateStateOnServer("lastUpdated", value=entity["last_updated"])
                if attributes.get('device_class', None) == 'temperature':
                    device.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
                elif attributes.get('device_class', None) == 'humidity':
                    device.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
                else:
                    device.updateStateImageOnServer(indigo.kStateImageSel.NoImage)
        elif device.deviceTypeId == "HAswitchType":
            if entity["last_updated"] != device.states['lastUpdated']:
                if entity["state"] == 'off':
                    device.updateStateOnServer("onOffState", value=False)
                else:
                    device.updateStateOnServer("onOffState", value=True)
                device.updateStateImageOnServer(indigo.kStateImageSel.NoImage)

        elif device.deviceTypeId == "HAdimmerType":
            if entity["last_updated"] != device.states['lastUpdated']:
                if entity["state"] == 'off':
                    device.updateStateOnServer("onOffState", value=False)
                else:
                    device.updateStateOnServer("onOffState", value=True)
                    brightness = attributes.get("brightness", 0) / 2.55
                    device.updateStateOnServer("brightnessLevel", value=round(brightness))
                device.updateStateImageOnServer(indigo.kStateImageSel.NoImage)

        else:
            self.logger.error(f"{device.name}: Unknown device type: {device.deviceTypeId}")

    ########################################
    # Relay/Dimmer Action methods
    ########################################
    def actionControlDimmerRelay(self, action, dev):
        headers = {'Authorization': f'Bearer {self.ha_token}', 'content-type': 'application/json'}
        post_data = {"entity_id": dev.address}
        self.logger.debug(f"{dev.name}: sending {action.deviceAction} to {dev.address}")

        if dev.deviceTypeId == "HAswitchType":
            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                url = f"http://{self.server_address}:{self.server_port}/api/services/switch/turn_on"  # noqa
                r = requests.post(url, headers=headers, json=post_data)

            elif action.deviceAction == indigo.kDimmerRelayAction.TurnOff:
                url = f"http://{self.server_address}:{self.server_port}/api/services/switch/turn_off"  # noqa
                r = requests.post(url, headers=headers, json=post_data)

        if dev.deviceTypeId == "HAdimmerType":
            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                url = f"http://{self.server_address}:{self.server_port}/api/services/light/turn_on"  # noqa
                r = requests.post(url, headers=headers, json=post_data)

            elif action.deviceAction == indigo.kDimmerRelayAction.TurnOff:
                url = f"http://{self.server_address}:{self.server_port}/api/services/light/turn_off"  # noqa
                r = requests.post(url, headers=headers, json=post_data)

            elif action.deviceAction == indigo.kDimmerRelayAction.SetBrightness:

                url = f"http://{self.server_address}:{self.server_port}/api/services/light/turn_on"  # noqa
                post_data = {"entity_id": dev.address, "brightness_pct": action.actionValue}
                r = requests.post(url, headers=headers, json=post_data)

    ########################################
    # Thermostat Action methods
    ########################################
    def actionControlThermostat(self, action, dev):
        headers = {'Authorization': f'Bearer {self.ha_token}', 'content-type': 'application/json'}
        if action.thermostatAction == indigo.kThermostatAction.SetHvacMode:
            self._handleChangeHvacModeAction(dev, action.actionMode)

        elif action.thermostatAction == indigo.kThermostatAction.SetFanMode:
            self._handleChangeFanModeAction(dev, action.actionMode)

        elif action.thermostatAction == indigo.kThermostatAction.SetCoolSetpoint:
            newSetpoint = action.actionValue
            self._handleChangeSetpointAction(dev, newSetpoint, "change cool setpoint", "setpointCool")

        elif action.thermostatAction == indigo.kThermostatAction.SetHeatSetpoint:
            newSetpoint = action.actionValue
            self._handleChangeSetpointAction(dev, newSetpoint, "change heat setpoint", "setpointHeat")

        elif action.thermostatAction == indigo.kThermostatAction.DecreaseCoolSetpoint:
            newSetpoint = dev.coolSetpoint - action.actionValue
            self._handleChangeSetpointAction(dev, newSetpoint, "decrease cool setpoint", "setpointCool")

        elif action.thermostatAction == indigo.kThermostatAction.IncreaseCoolSetpoint:
            newSetpoint = dev.coolSetpoint + action.actionValue
            self._handleChangeSetpointAction(dev, newSetpoint, "increase cool setpoint", "setpointCool")

        elif action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint:
            newSetpoint = dev.heatSetpoint - action.actionValue
            self._handleChangeSetpointAction(dev, newSetpoint, "decrease heat setpoint", "setpointHeat")

        elif action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint:
            newSetpoint = dev.heatSetpoint + action.actionValue
            self._handleChangeSetpointAction(dev, newSetpoint, "increase heat setpoint", "setpointHeat")

    ######################
    # Process action request from Indigo Server to change main thermostat's main mode.
    def _handleChangeHvacModeAction(self, device, newHvacMode):
        headers = {'Authorization': f'Bearer {self.ha_token}', 'content-type': 'application/json'}
        self.logger.debug(f"{device.name}: newHVACmode: {newHvacMode} ({HVAC_MODE_ENUM_TO_STR_MAP[newHvacMode]})")

        url = f"http://{self.server_address}:{self.server_port}/api/services/climate/set_hvac_mode"  # noqa
        post_data = {"entity_id": device.address, "hvac_mode": HVAC_MODE_ENUM_TO_STR_MAP[newHvacMode]}
        r = requests.post(url, headers=headers, json=post_data)

    def _handleChangeFanModeAction(self, device, newFanMode):
        headers = {'Authorization': f'Bearer {self.ha_token}', 'content-type': 'application/json'}
        self.logger.debug(f"{device.name}: newFanMode: {newFanMode} ({HVAC_MODE_ENUM_TO_STR_MAP[newFanMode]})")

        url = f"http://{self.server_address}:{self.server_port}/api/services/fan/set_fan_mode"  # noqa
        post_data = {"entity_id": device.address, "fan_mode": HVAC_MODE_ENUM_TO_STR_MAP[newFanMode]}
        r = requests.post(url, headers=headers, json=post_data)

    ######################
    # Process action request from Indigo Server to change a cool/heat setpoint.
    def _handleChangeSetpointAction(self, device, newSetpoint, logActionName, stateKey):
        headers = {'Authorization': f'Bearer {self.ha_token}', 'content-type': 'application/json'}

        if stateKey in ["setpointCool", "setpointHeat"]:
            url = f"http://{self.server_address}:{self.server_port}/api/services/climate/set_temperature"  # noqa
            post_data = {"entity_id": device.address, "temperature": newSetpoint}
            r = requests.post(url, headers=headers, json=post_data)
            self.logger.debug(f"{device.name}: _handleChangeSetpointAction: {stateKey} {newSetpoint:.1f}")

    ########################################
    # Plugin Menu object callbacks
    ########################################

    def dumpEntities(self):
        self.logger.info(f"\n{json.dumps(self.ha_entity_map, sort_keys=True, indent=4, separators=(',', ': '))}")
        return True

    ################################################################################
    # Minimal Websocket Client
    ################################################################################
    def ws_client(self, url):
        self.logger.debug(f"Connecting to '{url}'")

        self.ws = websocket.WebSocketApp(url, on_open=self.on_open,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)
        self.ws.run_forever(ping_interval=50, reconnect=5)

    def on_open(self, ws):
        self.logger.debug(f"Websocket connected")

    def on_message(self, ws, message):
        self.logger.threaddebug(f"Websocket on_message: {message}")
        msg = json.loads(message)

        if msg['type'] == 'auth_required':
            self.logger.debug(f"Websocket got auth_required for ha_version {msg['ha_version']}, sending auth_token")
            self.ws.send(json.dumps({'type': 'auth', 'access_token': self.ha_token}))

        elif msg['type'] == 'auth_ok':
            self.logger.debug(f"Websocket got auth_ok for ha_version {msg['ha_version']}")

            # subscribe to events
            self.send_ws('subscribe_events')

            # get states to populate devices, and build a list of the current home assistant entities
            self.send_ws('get_states')

        elif msg['type'] == 'auth_invalid':
            self.logger.error(f"Websocket got auth_invalid: {msg['message']}")

        elif msg['type'] == 'result':
            if msg['id'] in self.sent_messages:
                self.logger.debug(f"Websocket reply {'Success' if msg['success'] else 'Failed'} for {self.sent_messages[msg['id']]}")
                if self.sent_messages[msg['id']] == "subscribe_events":
                    pass

                elif self.sent_messages[msg['id']] == "get_states":
                    for entity in msg['result']:
                        self.logger.debug(f"Got states for {entity['entity_id']}, state = {entity.get('state', None)}")
                        self.update_device(entity['entity_id'], entity, force_update=True)
                    self.logger.debug(f"ha_entity_map: {json.dumps(self.ha_entity_map, indent=4, sort_keys=True)}")
                del self.sent_messages[msg['id']]

            else:
                self.logger.debug(f"Websocket got result for unknown message id: {msg['id']}")

        elif msg.get('type', None) == 'event' and msg['event'].get('event_type', None) == 'state_changed':
            try:
                self.update_device(msg['event']['data']['entity_id'], msg['event']['data']['new_state'])
            except Exception as e:
                self.logger.error(f"Websocket state_changed exception: {e}")
                self.logger.debug(f"Websocket state_changed:\n{msg}")

        elif msg.get('type', None) == 'event' and msg['event'].get('event_type', None) == 'lutron_caseta_button_event':
            self.logger.debug(
                f"Button event: {msg['event']['data']['serial']}: {msg['event']['data']['button_number']} {msg['event']['data']['action']}")

        elif (msg.get('type', None) == 'event' and
              msg['event'].get('event_type', None) in [
                  'recorder_5min_statistics_generated',
                  'recorder_hourly_statistics_generated',
                  'lovelace_updated',
                  'device_registry_updated',
                  'entity_registry_updated',
                  'service_registered',
                  'component_loaded',
                  'homeassistant_started',
                  'homeassistant_start',
                  'core_config_updated',
                  'call_service',
                  'config_entry_discovered',
                  'panels_updated',
                  'area_registry_updated',
                  'automation_triggered',
              ]):
            pass

        else:
            self.logger.debug(f"Websocket unknown message type: {json.dumps(msg)}")

    def send_ws(self, msg=None):
        self.last_sent_id += 1
        self.ws.send(json.dumps({'id': self.last_sent_id, 'type': msg}))
        self.sent_messages[self.last_sent_id] = msg

    def on_close(self, ws, close_status_code, close_msg):
        self.logger.debug(f"Websocket on_close: {close_status_code} {close_msg}")

    def on_error(self, ws, error):
        self.logger.debug(f"Websocket on_error: {error}")
