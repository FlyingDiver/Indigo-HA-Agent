#! /usr/bin/env python
# -*- coding: utf-8 -*-

import indigo
import requests
import logging
import websocket
import json
import threading
from zeroconf import IPVersion, ServiceBrowser, ServiceStateChange, Zeroconf

################################################################################
kHvacModeEnumToStrMap = {
    indigo.kHvacMode.Cool: "cool",
    indigo.kHvacMode.Heat: "heat",
    indigo.kHvacMode.HeatCool: "auto",
    indigo.kHvacMode.Off: "off",
    indigo.kHvacMode.ProgramHeat: "program heat",
    indigo.kHvacMode.ProgramCool: "program cool",
    indigo.kHvacMode.ProgramHeatCool: "program auto"
}

kHvacModeStrToEnumMap = {
    'heat': indigo.kHvacMode.Heat,
    'cool': indigo.kHvacMode.Cool,
    'auto': indigo.kHvacMode.HeatCool,
    'off': indigo.kHvacMode.Off
}

kFanModeEnumToStrMap = {
    indigo.kFanMode.AlwaysOn: "always on",
    indigo.kFanMode.Auto: "auto"
}

kFanModeStrToEnumMap = {
    'auto': indigo.kFanMode.Auto,
    'on': indigo.kFanMode.AlwaysOn
}


def _lookupActionStrFromHvacMode(hvacMode):
    return kHvacModeEnumToStrMap.get(hvacMode, "unknown")


def _lookupActionStrFromFanMode(fanMode):
    return kFanModeEnumToStrMap.get(fanMode, "unknown")


################################################################################

class Plugin(indigo.PluginBase):

    ########################################
    # Main Plugin Functions
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)

        self.thread = None
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
        self.thread = threading.Thread(target=self.ws_client, args=(ws_url,)).start()

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
        self.entity_devices[device.address] = device.id
        device.stateListOrDisplayStateIdChanged()

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

    def menuChanged(self, valuesDict, typeId, devId):
        self.logger.debug(f"menuChanged: typeId = {typeId}, devId = {devId}, valuesDict = {valuesDict}")
        valuesDict['address'] = valuesDict['found_list']
        return valuesDict

    def update_device(self, entity_id, new_states):
        device_id = self.entity_devices.get(entity_id, None)
        if not device_id:
            self.logger.debug(f"Ignoring update from entity `{entity_id}`, no matching Indigo device found")
            return

        device = indigo.devices[device_id]

        if new_states["last_updated"] == device.states['lastUpdated']:
            self.logger.debug(f"Device {device.name} already up to date")
            return

        attributes = new_states.get("attributes", None)
        if not attributes:
            self.logger.error(f"Device {device.name} no attributes")
            return

        self.logger.threaddebug(f"Updating device {device.name} with {new_states}")
        if device.deviceTypeId == "HAclimate":

            if new_states["last_updated"] != device.states['lastUpdated']:
                update_list = [
                    {'key': "setpointHeat", 'value': attributes["temperature"]},
                    {'key': "hvacOperationMode", 'value': kHvacModeStrToEnumMap[new_states["state"]]},
                    {'key': "temperatureInput1", 'value': attributes["current_temperature"]},
                    {'key': "lastUpdated", 'value': new_states["last_updated"]},
                ]
                device.updateStatesOnServer(update_list)
                device.updateStateImageOnServer(indigo.kStateImageSel.Auto)

        elif device.deviceTypeId == "HAbinarySensorType":
            if new_states["last_updated"] != device.states['lastUpdated']:
                if new_states["state"] == 'off':
                    device.updateStateOnServer("onOffState", value=False)
                else:
                    device.updateStateOnServer("onOffState", value=True)
                device.updateStateOnServer("lastUpdated", value=new_states["last_updated"])
                device.updateStateImageOnServer(indigo.kStateImageSel.Auto)

        elif device.deviceTypeId == "HAsensor":
            if new_states["last_updated"] != device.states['lastUpdated']:
                device.updateStateOnServer("sensorValue", value=new_states["state"])
                device.updateStateOnServer("lastUpdated", value=new_states["last_updated"])
                device.updateStateImageOnServer(indigo.kStateImageSel.Auto)

        elif device.deviceTypeId == "HAswitchType":
            if new_states["last_updated"] != device.states['lastUpdated']:
                if new_states["state"] == 'off':
                    device.updateStateOnServer("onOffState", value=False)
                else:
                    device.updateStateOnServer("onOffState", value=True)
                device.updateStateImageOnServer(indigo.kStateImageSel.Auto)

        elif device.deviceTypeId == "HAdimmerType":
            if new_states["last_updated"] != device.states['lastUpdated']:
                if new_states["state"] == 'off':
                    device.updateStateOnServer("onOffState", value=False)
                else:
                    device.updateStateOnServer("onOffState", value=True)
                    brightness = attributes.get("brightness", 0) / 2.55
                    device.updateStateOnServer("brightnessLevel", value=round(brightness))
                device.updateStateImageOnServer(indigo.kStateImageSel.Auto)

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
    def _handleChangeHvacModeAction(self, dev, newHvacMode):
        headers = {'Authorization': f'Bearer {self.ha_token}', 'content-type': 'application/json'}

        if newHvacMode == 0:
            newHvacModeHA = 'off'
        else:
            newHvacModeHA = 'heat'
        self.logger.info(f"newHVACmode: {newHvacModeHA}")

        url = f"http://{self.server_address}:{self.server_port}/api/services/climate/set_operation_mode"  # noqa
        newHvacModeHA = action.actionValue
        post_data = {"entity_id": dev.address, "operation_mode": newHvacModeHA}
        r = requests.post(url, headers=headers, json=post_data)

        actionStr = _lookupActionStrFromHvacMode(newHvacMode)
        self.logger.debug(f"sent \"{dev.name}\" mode change to {actionStr}")
        if "hvacOperationMode" in dev.states:
            dev.updateStateOnServer("hvacOperationMode", newHvacMode)

    ######################
    # Process action request from Indigo Server to change a cool/heat setpoint.
    def _handleChangeSetpointAction(self, dev, newSetpoint, logActionName, stateKey):
        headers = {'Authorization': f'Bearer {self.ha_token}', 'content-type': 'application/json'}

        url = f"http://{self.server_address}:{self.server_port}/api/states/{dev.address}"  # noqa
        ha_device = requests.get(url, headers=headers).json()
        self.logger.debug(f"Device content:\n{ha_device}")
        att = ha_device["attributes"]
        SetpointMaxHA = att["max_temp"]
        SetpointMinHA = att["min_temp"]

        if newSetpoint < SetpointMinHA:
            newSetpoint = SetpointMinHA  # Arbitrary -- set to whatever hardware minimum setpoint value is.
        elif newSetpoint > SetpointMaxHA:
            newSetpoint = SetpointMaxHA  # Arbitrary -- set to whatever hardware maximum setpoint value is.

        if stateKey in ["setpointCool", "setpointHeat"]:
            url = f"http://{self.server_address}:{self.server_port}/api/services/climate/set_temperature"  # noqa
            newHvacModeHA = action.actionValue
            post_data = {"entity_id": dev.address, "temperature": newSetpoint}
            r = requests.post(url, headers=headers, json=post_data)
            self.logger.debug(f"sent \"{dev.name}\" {logActionName} to {newSetpoint:.1f}°")

        if stateKey in dev.states:
            dev.updateStateOnServer(stateKey, float(newSetpoint), uiValue=f"{newSetpoint:.1f} °F")

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
        self.logger.debug(f"Websocket on_open")

    def on_message(self, ws, message):
        self.logger.threaddebug(f"Websocket on_message: {message}")
        msg = json.loads(message)

        if msg['type'] == 'auth_required':
            self.logger.debug(f"Websocket got auth_required for ha_version {msg['ha_version']}, sending auth_token")
            self.ws.send(json.dumps({'type': 'auth', 'access_token': self.ha_token}))

        elif msg['type'] == 'auth_ok':
            self.logger.debug(f"Websocket got auth_ok for ha_version {msg['ha_version']}")

            # subscribe to events
            self.last_sent_id += 1
            self.ws.send(json.dumps({'id': self.last_sent_id, 'type': 'subscribe_events'}))
            self.sent_messages[self.last_sent_id] = "subscribe_events"

            # get states to populate devices, and build a list of the current home assistant entities
            self.last_sent_id += 1
            self.ws.send(json.dumps({'id': self.last_sent_id, 'type': 'get_states'}))
            self.sent_messages[self.last_sent_id] = "get_states"

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
                        self.update_device(entity['entity_id'], entity)
                        parts = entity['entity_id'].split('.')
                        if parts[0] not in self.ha_entity_map:
                            self.ha_entity_map[parts[0]] = {}
                        self.ha_entity_map[parts[0]][parts[1]] = entity['entity_id']
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
              ]):
            pass

        else:
            self.logger.debug(f"Websocket unknown message type: {json.dumps(msg)}")

    def on_close(self, ws, close_status_code, close_msg):
        self.logger.debug(f"Websocket on_close: {close_status_code} {close_msg}")

    def on_error(self, ws, error):
        self.logger.debug(f"Websocket on_error: {error}")
