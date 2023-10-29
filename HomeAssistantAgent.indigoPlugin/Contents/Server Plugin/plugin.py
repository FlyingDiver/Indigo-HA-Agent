#! /usr/bin/env python
# -*- coding: utf-8 -*-

import indigo
import logging
import json
import threading
import websocket
from enum import IntFlag

try:
    from zeroconf import IPVersion, ServiceBrowser, ServiceStateChange, Zeroconf
except ImportError:
    raise ImportError("'Required Python libraries missing.  Run 'pip3 install zeroconf' in Terminal window, then reload plugin.")


def _update_indigo_var(name, value, folder):
    if name not in indigo.variables:
        indigo.variable.create(name, value, folder)
    else:
        indigo.variable.updateValue(name, value)

def is_number(input_str):
    try:
        float(input_str)
        return True
    except ValueError:
        return False

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
    'off': indigo.kHvacMode.Off,
    'unavailable': indigo.kHvacMode.Off
}

FAN_MODE_ENUM_TO_STR_MAP = {
    indigo.kFanMode.AlwaysOn: "always on",
    indigo.kFanMode.Auto: "auto"
}

FAN_MODE_STR_TO_ENUM_MAP = {
    'auto': indigo.kFanMode.Auto,
    'on': indigo.kFanMode.AlwaysOn
}


def _lookup_action_str_from_hvac_mode(hvac_mode):
    return HVAC_MODE_ENUM_TO_STR_MAP.get(hvac_mode, "unknown")


def _lookup_action_str_from_fan_mode(fan_mode):
    return FAN_MODE_ENUM_TO_STR_MAP.get(fan_mode, "unknown")


def _lookup_hvac_mode_from_action_str(hvac_mode):
    return HVAC_MODE_STR_TO_ENUM_MAP.get(hvac_mode.lower(), indigo.kHvacMode.Off)


def _lookup_fan_mode_from_action_str(fan_mode):
    return FAN_MODE_STR_TO_ENUM_MAP.get(fan_mode.lower(), indigo.kFanMode.Auto)

# Home Assistant Features
class CoverEntityFeature(IntFlag):
    """Supported features of the cover entity."""
    OPEN = 1
    CLOSE = 2
    SET_POSITION = 4
    STOP = 8
    OPEN_TILT = 16
    CLOSE_TILT = 32
    STOP_TILT = 64
    SET_TILT_POSITION = 128

class ClimateEntityFeature(IntFlag):
    """Supported features of the climate entity."""
    TARGET_TEMPERATURE = 1
    TARGET_TEMPERATURE_RANGE = 2
    TARGET_HUMIDITY = 4
    FAN_MODE = 8
    PRESET_MODE = 16
    SWING_MODE = 32
    AUX_HEAT = 64

class LightEntityFeature(IntFlag):
    """Supported features of the light entity."""
    EFFECT = 4
    FLASH = 8
    TRANSITION = 32

class FanEntityFeature(IntFlag):
    """Supported features of the fan entity."""
    SET_SPEED = 1
    OSCILLATE = 2
    DIRECTION = 4
    PRESET_MODE = 8

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
        self.var_folder = None
        self.found_ha_servers = {}
        self.entity_devices = {}
        self.sent_messages = {}
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

        zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        services = ["_home-assistant._tcp.local."]
        browser = ServiceBrowser(zeroconf, services, handlers=[self.on_service_state_change])

        # start up the websocket receiver thread
        ws_url = f"ws://{self.server_address}:{self.server_port}/api/websocket"
        self.websocket_thread = threading.Thread(target=self.ws_client, args=(ws_url,)).start()

        # get the folder for the event variables
        if "HAA_Event" in indigo.variables.folders:
            self.var_folder = indigo.variables.folders["HAA_Event"]
        else:
            self.var_folder = indigo.variables.folder.create("HAA_Event")

    def on_service_state_change(self, zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        self.logger.debug(f"Service {name} of type {service_type} state changed: {state_change}")
        info = zeroconf.get_service_info(service_type, name)
        ip_address = ".".join([f"{x}" for x in info.addresses[0]])  # address as string (xx.xx.xx.xx)

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
        self.logger.info(f"{device.name}: Starting Agent device for entity '{device.address}'")
        self.entity_devices[device.address] = device.id
        parts = device.address.split('.')
        try:
            entity = self.ha_entity_map[parts[0]][parts[1]]
        except Exception as err:
            self.logger.debug(f"{device.name}: {device.address} not in ha_entity_map[{parts[0]}][{parts[1]}]")
            return

        new_props = device.pluginProps
        features = entity['attributes'].get('supported_features', 0)

        # check the attributes for the device and update the Indigo device definition
        if device.deviceTypeId == "HAclimate":

            if features & ClimateEntityFeature.TARGET_TEMPERATURE:
                new_props["NumTemperatureInputs"] = 1
            if features & ClimateEntityFeature.TARGET_HUMIDITY:
                new_props["NumHumidityInputs"] = 1
            if features & ClimateEntityFeature.FAN_MODE:
                new_props["SupportsHvacFanMode"] = True
            if 'heat' in entity['attributes']['hvac_modes']:
                new_props["SupportsHeatSetpoint"] = True
            if 'cool' in entity['attributes']['hvac_modes']:
                new_props["SupportsCoolSetpoint"] = True

        elif device.deviceTypeId == "ha_cover":

            if features & CoverEntityFeature.SET_POSITION:
                new_props["SupportsSetPosition"] = True
            if features & CoverEntityFeature.STOP:
                new_props["SupportsStop"] = True
            if features & CoverEntityFeature.OPEN_TILT:
                new_props["SupportsOpenTilt"] = True
            if features & CoverEntityFeature.CLOSE_TILT:
                new_props["SupportsCloseTilt"] = True
            if features & CoverEntityFeature.STOP_TILT:
                new_props["SupportsStopTilt"] = True
            if features & CoverEntityFeature.SET_TILT_POSITION:
                new_props["SupportsSetTiltPosition"] = True

        elif device.deviceTypeId == "ha_fan":

            if features & FanEntityFeature.DIRECTION:
                new_props["SupportsSetDirection"] = True
            if features & FanEntityFeature.OSCILLATE:
                new_props["SupportsOscillate"] = True
            if features & FanEntityFeature.PRESET_MODE:
                new_props["SupportsFanPresetMode"] = True
            if features & FanEntityFeature.SET_SPEED:
                new_props["SupportsFanSpeed"] = True

        device.replacePluginPropsOnServer(new_props)
        device.stateListOrDisplayStateIdChanged()
        self.entity_update(entity['entity_id'], entity, force_update=True)  # force update of Indigo device

    def deviceStopComm(self, device):
        self.logger.info(f"{device.name}: Stopping Agent device for entity '{device.address}'")
        del self.entity_devices[device.address]

    @staticmethod
    def didDeviceCommPropertyChange(oldDevice, newDevice):
        if oldDevice.address != newDevice.address:
            return True
        return False

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

    def get_entity_type_list(self, filter="", valuesDict=None, typeId="", targetId=0):
        self.logger.debug(f"get_entity_type_list: {filter = }, {typeId = }, {valuesDict = }, {targetId = }")

        retList = []
        for entity_type, entity_list in self.ha_entity_map.items():
            if entity_type not in ['climate', 'cover', 'light', 'sensor', 'switch', 'binary_sensor']:
                retList.append((entity_type, entity_type))
        retList.sort(key=lambda tup: tup[1])
        self.logger.debug(f"get_entity_type_list: {retList = }")
        return retList

    def get_entity_list(self, filter="", valuesDict=None, typeId="", targetId=0):
        self.logger.debug(f"get_entity_list: {filter = }, {typeId = }, {valuesDict = }, {targetId = }")
        if filter == "generic":
            filter = valuesDict.get('entity_type', None)

        retList = []
        if not filter:
            return retList

        for entity_name, entity in self.ha_entity_map[filter].items():
            retList.append((entity['entity_id'], entity_name))
        retList.sort(key=lambda tup: tup[1])
        self.logger.debug(f"get_entity_list for filter '{filter}': {retList = }")
        return retList

    def menuChanged(self, valuesDict, typeId, devId):
        self.logger.debug(f"menuChanged: {typeId = }, {devId = }, {valuesDict = }")
        return valuesDict

    def getDeviceStateList(self, device):
        stateList = indigo.PluginBase.getDeviceStateList(self, device)
        add_states = device.pluginProps.get("states_list", indigo.List())
        for key in add_states:
            new_state = self.getDeviceStateDictForStringType(str(key), str(key), str(key))
            stateList.append(new_state)
        self.logger.threaddebug(f"{device.name}: getDeviceStateList returning: {stateList}")
        return stateList

    def entity_update(self, entity_id, entity, force_update=False):
        parts = entity_id.split('.')

        # check for deleted entity
        if entity is None:
            del self.ha_entity_map[parts[0]][parts[1]]
            return

        # save the entity state info in the entity map
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

        states_list = []
        old_states = device.pluginProps.get("states_list", indigo.List())
        new_states = indigo.List()
        for key in attributes:
            self.logger.threaddebug(f"{device.name}: adding to states_list: {key}, {attributes[key]}, {type(attributes[key])}")
            new_states.append(key)
            if type(attributes[key]) in (int, bool, str):
                states_list.append({'key': key, 'value': attributes[key]})
            elif type(attributes[key]) is float:
                states_list.append({'key': key, 'value': attributes[key], 'decimalPlaces': 2})
            else:
                states_list.append({'key': key, 'value': json.dumps(attributes[key])})

        if set(old_states) != set(new_states):
            self.logger.debug(f"{device.name}: states list changed, updating...")
            newProps = device.pluginProps
            newProps["states_list"] = new_states
            device.replacePluginPropsOnServer(newProps)
            device.stateListOrDisplayStateIdChanged()
            self.sleep(1.0)
        device.updateStatesOnServer(states_list)

        if device.deviceTypeId == "HAclimate":

            if entity["last_updated"] != device.states['lastUpdated']:
                update_list = [
                    {'key': "hvacOperationMode", 'value': _lookup_hvac_mode_from_action_str(entity["state"])},
                    {'key': "hvac_mode", 'value': entity["state"]},
                    {'key': "lastUpdated", 'value': entity["last_updated"]},
                    {'key': "actual_state", 'value': entity["state"]}
                ]

                # HA setpoints are wonky

                if attributes.get("temperature", None):
                    if 'heat' in attributes['hvac_modes']:
                        update_list.append({'key': "setpointHeat", 'value': attributes["temperature"]})
                    if 'cool' in attributes['hvac_modes']:
                        update_list.append({'key': "setpointCool", 'value': attributes["temperature"]})
                elif attributes.get('target_temp_high', None) and attributes.get('target_temp_low', None):
                    if 'heat' in attributes['hvac_modes']:
                        update_list.append({'key': "setpointHeat", 'value': attributes["target_temp_low"]})
                    if 'cool' in attributes['hvac_modes']:
                        update_list.append({'key': "setpointCool", 'value': attributes["target_temp_high"]})

                if attributes.get("preset_mode", None):
                    update_list.append({'key': "preset_mode", 'value': attributes["preset_mode"]})
                else:
                    update_list.append({'key': "preset_mode", 'value': ""})

                if attributes.get("preset_modes", None):
                    update_list.append({'key': "preset_modes", 'value': ", ".join(attributes["preset_modes"])})
                else:
                    update_list.append({'key': "preset_modes", 'value': ""})

                if attributes.get("hvac_modes", None):
                    update_list.append({'key': "hvac_modes", 'value': ", ".join(attributes["hvac_modes"])})
                else:
                    update_list.append({'key': "hvac_modes", 'value': ""})

                if attributes.get("hvac_action", None):
                    update_list.append({'key': "hvacCoolerIsOn", 'value': attributes["hvac_action"] == "cooling"})
                    update_list.append({'key': "hvacHeaterIsOn", 'value': attributes["hvac_action"] == "heating"})
                    update_list.append({'key': "hvac_action", 'value': attributes["hvac_action"]})
                else:
                    update_list.append({'key': "hvac_action", 'value': ""})

                if attributes.get("fan_mode", None):
                    update_list.append({'key': "hvacFanMode", 'value': _lookup_fan_mode_from_action_str(attributes["fan_mode"])})
                    update_list.append({'key': "hvacFanIsOn", 'value': attributes["fan_mode"] == "on"})
                    update_list.append({'key': "fan_mode", 'value': attributes["fan_mode"]})
                else:
                    update_list.append({'key': "fan_mode", 'value': ""})

                if attributes.get("fan_modes", None):
                    update_list.append({'key': "fan_modes", 'value': ", ".join(attributes["fan_modes"])})
                else:
                    update_list.append({'key': "fan_modes", 'value': ""})

                if attributes.get("swing_mode", None):
                    update_list.append({'key': "swing_mode", 'value': attributes["swing_mode"]})
                else:
                    update_list.append({'key': "swing_mode", 'value': ""})

                if attributes.get("swing_modes", None):
                    update_list.append({'key': "swing_modes", 'value': ", ".join(attributes["swing_modes"])})
                else:
                    update_list.append({'key': "swing_modes", 'value': ""})

                if attributes.get("current_temperature", None):
                    update_list.append({'key': "temperatureInput1", 'value': attributes["current_temperature"],
                                        'uiValue': f"{attributes['current_temperature']}\u00b0F"})

                if attributes.get("current_humidity", None):
                    update_list.append({'key': "humidityInput1", 'value': attributes["current_humidity"],
                                        'uiValue': f"{attributes['current_humidity']}%"})

                try:
                    self.logger.threaddebug(f"do_update: update_list: {update_list}")
                    device.updateStatesOnServer(update_list)
                except Exception as e:
                    self.logger.error(f"{device.name}: failed to update states: {e}")

        elif device.deviceTypeId == "HAbinarySensorType":
            if entity["last_updated"] != device.states['lastUpdated']:
                if isOff := entity["state"] == 'off':
                    device.updateStateOnServer("onOffState", value=False)
                else:
                    device.updateStateOnServer("onOffState", value=True)
                device.updateStateOnServer("lastUpdated", value=entity["last_updated"])
                device.updateStateOnServer("lastUpdated", value=entity["last_updated"])
                device.updateStateOnServer("actual_state", value=entity["state"])
                if attributes.get('device_class', None) == 'occupancy':
                    device.updateStateImageOnServer(indigo.kStateImageSel.MotionSensor if isOff else indigo.kStateImageSel.MotionSensorTripped)
                elif attributes.get('device_class', None) == 'problem':
                    device.updateStateImageOnServer(indigo.kStateImageSel.SensorOn if isOff else indigo.kStateImageSel.SensorTripped)
                else:
                    device.updateStateImageOnServer(indigo.kStateImageSel.NoImage)

        elif device.deviceTypeId == "HAsensor":
            if entity["last_updated"] != device.states['lastUpdated']:
                units = attributes.get("unit_of_measurement", "")
                state_value = entity["state"]
                if is_number(state_value):
                    device.updateStateOnServer("sensorValue", value=state_value, uiValue=f"{state_value}{units}")
                else:
                    self.logger.threaddebug(f"do_update: forcing value to 0.0 for : {device.name}")
                    device.updateStateOnServer("sensorValue", value=0.0, uiValue=state_value)
                device.updateStateOnServer("lastUpdated", value=entity["last_updated"])
                device.updateStateOnServer("actual_state", value=entity["state"])
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
                device.updateStateOnServer("lastUpdated", value=entity["last_updated"])
                device.updateStateOnServer("actual_state", value=entity["state"])
                device.updateStateImageOnServer(indigo.kStateImageSel.NoImage)

        elif device.deviceTypeId == "HAdimmerType":
            if entity["last_updated"] != device.states['lastUpdated']:
                if entity["state"] == 'off':
                    device.updateStateOnServer("onOffState", value=False)
                else:
                    device.updateStateOnServer("onOffState", value=True)
                    position = attributes.get("position", 0)
                    device.updateStateOnServer("brightnessLevel", value=round(position))
                device.updateStateOnServer("lastUpdated", value=entity["last_updated"])
                device.updateStateOnServer("actual_state", value=entity["state"])
                device.updateStateImageOnServer(indigo.kStateImageSel.NoImage)

        elif device.deviceTypeId == "ha_cover":
            if entity["last_updated"] != device.states['lastUpdated']:
                if entity["state"] == 'closed':
                    device.updateStateOnServer("onOffState", value=False, uiValue="Closed")
                else:
                    device.updateStateOnServer("onOffState", value=True, uiValue=entity["state"].capitalize())
                device.updateStateOnServer("lastUpdated", value=entity["last_updated"])
                device.updateStateOnServer("actual_state", value=entity["state"])
                device.updateStateImageOnServer(indigo.kStateImageSel.NoImage)

        elif device.deviceTypeId == "ha_fan":
            speed_index_scale_factor = int(100 / (device.speedIndexCount - 1))
            if entity["last_updated"] != device.states['lastUpdated']:
                if entity["state"] == 'off':
                    device.updateStateOnServer("onOffState", value=False, uiValue="Off")
                else:
                    speed_percentage = attributes.get("percentage", 0)
                    speed_index = round(speed_percentage / speed_index_scale_factor)
                    device.updateStateOnServer("onOffState", value=True, uiValue="On")
                    device.updateStateOnServer("speedIndex", speed_index)
                device.updateStateOnServer("lastUpdated", value=entity["last_updated"])
                device.updateStateOnServer("actual_state", value=entity["state"])
                device.updateStateImageOnServer(indigo.kStateImageSel.NoImage)

        elif device.deviceTypeId == "ha_generic":
            device.updateStateOnServer("lastUpdated", value=entity["last_updated"])
            device.updateStateOnServer("actual_state", value=entity["state"])
            device.updateStateImageOnServer(indigo.kStateImageSel.NoImage)

        else:
            self.logger.error(f"{device.name}: Unknown device type: {device.deviceTypeId} in entity_update()")

    ########################################
    # Relay/Dimmer Action methods
    ########################################
    def actionControlDimmerRelay(self, action, device):
        self.logger.debug(f"{device.name}: sending {action.deviceAction} to {device.address}")
        msg_data = {"type": "call_service", "target": {"entity_id": device.address}}

        if device.deviceTypeId == "HAswitchType":
            msg_data['domain'] = 'switch'
            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                msg_data['service'] = 'turn_on'
                self.send_ws(msg_data)

            elif action.deviceAction == indigo.kDimmerRelayAction.TurnOff:
                msg_data['service'] = 'turn_off'
                self.send_ws(msg_data)

            elif action.deviceAction == indigo.kDimmerRelayAction.Toggle:
                msg_data['service'] = 'toggle'
                self.send_ws(msg_data)

        if device.deviceTypeId == "HAdimmerType":
            msg_data['domain'] = 'light'
            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                msg_data['service'] = 'turn_on'
                self.send_ws(msg_data)

            elif action.deviceAction == indigo.kDimmerRelayAction.TurnOff:
                msg_data['service'] = 'turn_off'
                self.send_ws(msg_data)

            elif action.deviceAction == indigo.kDimmerRelayAction.SetBrightness:
                msg_data['service'] = 'turn_on'
                msg_data['service_data'] = {"brightness_pct": action.actionValue}
                self.send_ws(msg_data)

        if device.deviceTypeId == "ha_cover":
            msg_data['domain'] = 'cover'
            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                msg_data['service'] = 'open_cover'
                self.send_ws(msg_data)

            elif action.deviceAction == indigo.kDimmerRelayAction.TurnOff:
                msg_data['service'] = 'close_cover'
                self.send_ws(msg_data)

    ########################################
    # Thermostat Action methods
    ########################################
    def actionControlThermostat(self, action, device):
        if action.thermostatAction == indigo.kThermostatAction.SetHvacMode:
            self.logger.debug(f"{device.name}: newHVACmode: {action.actionMode} ({_lookup_action_str_from_hvac_mode(action.actionMode)})")
            msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'climate', 'service': 'set_hvac_mode',
                        'service_data': {"hvac_mode": _lookup_action_str_from_hvac_mode(action.actionMode)}}
            self.send_ws(msg_data)

        elif action.thermostatAction == indigo.kThermostatAction.SetCoolSetpoint:
            newSetpoint = action.actionValue
            self._handleChangeSetpointAction(device, newSetpoint, "setpointCool")

        elif action.thermostatAction == indigo.kThermostatAction.SetHeatSetpoint:
            newSetpoint = action.actionValue
            self._handleChangeSetpointAction(device, newSetpoint, "setpointHeat")

        elif action.thermostatAction == indigo.kThermostatAction.DecreaseCoolSetpoint:
            newSetpoint = device.coolSetpoint - action.actionValue
            self._handleChangeSetpointAction(device, newSetpoint, "setpointCool")

        elif action.thermostatAction == indigo.kThermostatAction.IncreaseCoolSetpoint:
            newSetpoint = device.coolSetpoint + action.actionValue
            self._handleChangeSetpointAction(device, newSetpoint, "setpointCool")

        elif action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint:
            newSetpoint = device.heatSetpoint - action.actionValue
            self._handleChangeSetpointAction(device, newSetpoint, "setpointHeat")

        elif action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint:
            newSetpoint = device.heatSetpoint + action.actionValue
            self._handleChangeSetpointAction(device, newSetpoint, "setpointHeat")

        elif action.thermostatAction == indigo.kThermostatAction.SetFanMode:
            self.logger.debug(f"{device.name}: fanMode: {action.actionMode} ({_lookup_action_str_from_fan_mode(action.actionMode)})")
            msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'climate', 'service': 'set_fan_mode',
                        'service_data': {"fan_mode": _lookup_action_str_from_fan_mode(action.actionMode)}}
            self.send_ws(msg_data)

    ########################################
    # Speed Control Action callbacks
    ######################
    def actionControlSpeedControl(self, action, device):
        self.logger.debug(f"{device.name}: sending {action.speedControlAction} {action.actionValue} to {device.address}")
        msg_data = {"type": "call_service", "domain": 'fan', "target": {"entity_id": device.address}}
        speed_index_scale_factor = int(100 / (device.speedIndexCount -1))

        if action.speedControlAction == indigo.kSpeedControlAction.TurnOn:
            msg_data['service'] = 'turn_on'
            self.send_ws(msg_data)

        elif action.speedControlAction == indigo.kSpeedControlAction.TurnOff:
            msg_data['service'] = 'turn_off'
            self.send_ws(msg_data)

        elif action.speedControlAction == indigo.kSpeedControlAction.Toggle:
            msg_data['service'] = 'turn_off' if device.onState else 'turn_on'
            self.send_ws(msg_data)

        elif action.speedControlAction == indigo.kSpeedControlAction.SetSpeedLevel:
            msg_data['service'] = 'set_percentage'
            msg_data['service_data'] = {"percentage": action.actionValue}
            self.send_ws(msg_data)

        elif action.speedControlAction == indigo.kSpeedControlAction.SetSpeedIndex:
            msg_data['service'] = 'set_percentage'
            msg_data['service_data'] = {"percentage": str(int(action.actionValue) * speed_index_scale_factor)}
            self.send_ws(msg_data)

        elif action.speedControlAction == indigo.kSpeedControlAction.IncreaseSpeedIndex:
            speedIndex = min(device.speedIndex + 1, device.speedIndexCount - 1)
            msg_data['service'] = 'set_percentage'
            msg_data['service_data'] = {"percentage": str(speedIndex * speed_index_scale_factor)}
            self.send_ws(msg_data)

        elif action.speedControlAction == indigo.kSpeedControlAction.DecreaseSpeedIndex:
            speedIndex = max(device.speedIndex - 1, 0)
            msg_data['service'] = 'set_percentage'
            msg_data['service_data'] = {"percentage": str(speedIndex * speed_index_scale_factor)}
            self.send_ws(msg_data)
        self.logger.debug(f"{device.name}: sent {msg_data} to {device.address}")

    # Process action request from Indigo Server to change a cool/heat setpoint.
    def _handleChangeSetpointAction(self, device, newSetpoint, stateKey):
        if stateKey in ["setpointCool", "setpointHeat"]:
            self.logger.debug(f"{device.name}: _handleChangeSetpointAction: {stateKey} {newSetpoint:.1f}")
            msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'climate', 'service': 'set_temperature',
                        'service_data': {"temperature": newSetpoint}}
            self.send_ws(msg_data)

    ########################################
    # Plugin Menu object callbacks
    ########################################

    def dumpEntities(self):
        self.logger.info(f"\n{json.dumps(self.ha_entity_map, sort_keys=True, indent=4, separators=(',', ': '))}")
        return True

    def get_states(self):
        self.send_ws({"type": 'get_states'})
        return True

    ########################################
    # Action callbacks
    ########################################

    def hvac_mode_list(self, filter, values_dict, type_id, target_id):
        self.logger.debug(f"hvac_mode_list: type_id = {type_id}, target_id = {target_id}")
        device = indigo.devices[target_id]
        parts = device.address.split('.')
        try:
            entity = self.ha_entity_map[parts[0]][parts[1]]
        except Exception as err:
            self.logger.debug(f"{device.name}: {device.address} not in ha_entity_map[{parts[0]}][{parts[1]}]")
            return

        if entity['attributes'].get('hvac_modes', None):
            return [(preset, preset) for preset in entity['attributes']['hvac_modes']]
        else:
            return []

    def set_hvac_mode_action(self, plugin_action, device, callerWaitingForResult):
        mode = plugin_action.props.get("hvac_mode", None)
        self.logger.debug(f"{device.name}: set_hvac_mode_action: {mode} for {device.address}")
        if mode:
            msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'climate', 'service': 'set_hvac_mode',
                        'service_data': {"hvac_mode": mode}}
            self.send_ws(msg_data)

    def hvac_fan_mode_list(self, filter, values_dict, type_id, target_id):
        self.logger.debug(f"fan_mode_list: type_id = {type_id}, target_id = {target_id}")
        device = indigo.devices[target_id]
        parts = device.address.split('.')
        try:
            entity = self.ha_entity_map[parts[0]][parts[1]]
        except Exception as err:
            self.logger.debug(f"{device.name}: {device.address} not in ha_entity_map[{parts[0]}][{parts[1]}]")
            return

        if entity['attributes'].get('fan_modes', None):
            return [(preset, preset) for preset in entity['attributes']['fan_modes']]
        else:
            return []

    def set_hvac_fan_mode_action(self, plugin_action, device, callerWaitingForResult):
        mode = plugin_action.props.get("fan_mode", None)
        self.logger.debug(f"{device.name}: set_fan_mode_action: {mode} for {device.address}")
        if mode:
            msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'climate', 'service': 'set_fan_mode',
                        'service_data': {"fan_mode": mode}}
            self.send_ws(msg_data)

    def hvac_swing_mode_list(self, filter, values_dict, type_id, target_id):
        self.logger.debug(f"swing_mode_list: type_id = {type_id}, target_id = {target_id}")
        device = indigo.devices[target_id]
        parts = device.address.split('.')
        try:
            entity = self.ha_entity_map[parts[0]][parts[1]]
        except Exception as err:
            self.logger.debug(f"{device.name}: {device.address} not in ha_entity_map[{parts[0]}][{parts[1]}]")
            return

        if entity['attributes'].get('swing_modes', None):
            return [(preset, preset) for preset in entity['attributes']['swing_modes']]
        else:
            return []

    def set_hvac_swing_mode_action(self, plugin_action, device, callerWaitingForResult):
        mode = plugin_action.props.get("hvac_swing_mode", None)
        self.logger.debug(f"{device.name}: set_hvac_swing_mode_action: {mode} for {device.address}")
        if mode:
            msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'climate', 'service': 'set_swing_mode',
                        'service_data': {"swing_mode": mode}}
            self.send_ws(msg_data)

    def hvac_preset_mode_list(self, filter, values_dict, type_id, target_id):
        self.logger.debug(f"preset_mode_list: type_id = {type_id}, target_id = {target_id}")
        device = indigo.devices[target_id]
        parts = device.address.split('.')
        try:
            entity = self.ha_entity_map[parts[0]][parts[1]]
        except Exception as err:
            self.logger.debug(f"{device.name}: {device.address} not in ha_entity_map[{parts[0]}][{parts[1]}]")
            return

        if entity['attributes'].get('preset_modes', None):
            return [(preset, preset) for preset in entity['attributes']['preset_modes']]
        else:
            return []

    def set_hvac_preset_mode_action(self, plugin_action, device, callerWaitingForResult):
        mode = plugin_action.props.get("hvac_preset_mode", None)
        self.logger.debug(f"{device.name}: set_hvac_preset_mode_action: {mode} for {device.address}")
        if mode:
            msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'climate', 'service': 'set_preset_mode',
                        'service_data': {"preset_mode": mode}}
            self.send_ws(msg_data)

    def set_humidity_action(self, plugin_action, device, callerWaitingForResult):
        humidity = plugin_action.props.get("hvac_humidity", None)
        self.logger.debug(f"{device.name}: set_humidity_action: {humidity} for {device.address}")
        if humidity:
            msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'climate', 'service': 'set_humidity',
                        'service_data': {"humidity": humidity}}
            self.send_ws(msg_data)

    #   Cover entity actions

    def set_cover_position_action(self, plugin_action, device, callerWaitingForResult):
        self.logger.debug(f"{device.name}: set_cover_position_action for {device.address}")
        if not device.pluginProps.get("SupportsSetPosition", None):
            self.logger.warning(f"{device.name}: set_cover_position_action: {device.address} does not support set cover position")
            return
        msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'cover',
                    'service': 'set_cover_position', 'service_data': {"position": plugin_action.props.get("cover_position", 0)}}
        self.send_ws(msg_data)

    def stop_cover_action(self, plugin_action, device, callerWaitingForResult):
        self.logger.debug(f"{device.name}: stop_cover_action for {device.address}")
        if not device.pluginProps.get("SupportsStop", None):
            self.logger.warning(f"{device.name}: stop_cover_action: {device.address} does not support stop cover")
            return
        msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'cover', 'service': 'stop_cover'}
        self.send_ws(msg_data)

    def open_cover_tilt_action(self, plugin_action, device, callerWaitingForResult):
        self.logger.debug(f"{device.name}: open_cover_tilt_action for {device.address}")
        if not device.pluginProps.get("SupportsOpenTilt", None):
            self.logger.warning(f"{device.name}: open_cover_tilt_action: {device.address} does not support open tilt")
            return
        msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'cover', 'service': 'open_cover_tilt'}
        self.send_ws(msg_data)

    def close_cover_tilt_action(self, plugin_action, device, callerWaitingForResult):
        self.logger.debug(f"{device.name}: close_cover_tilt_action for {device.address}")
        if not device.pluginProps.get("SupportsCloseTilt", None):
            self.logger.warning(f"{device.name}: close_cover_tilt_action: {device.address} does not support close tilt")
            return
        msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'cover', 'service': 'close_cover_tilt'}
        self.send_ws(msg_data)

    def set_cover_tilt_position_action(self, plugin_action, device, callerWaitingForResult):
        self.logger.debug(f"{device.name}: set_cover_tilt_position_action for {device.address}")
        if not device.pluginProps.get("SupportsSetTiltPosition", None):
            self.logger.warning(f"{device.name}: set_cover_tilt_position_action: {device.address} does not support set tilt")
            return
        msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'cover',
                    'service': 'set_cover_tilt_position', 'service_data': {"position": plugin_action.props.get("tilt_position", 0)}}
        self.send_ws(msg_data)

    #   Fan entity actions

    def set_fan_direction_action(self, plugin_action, device, callerWaitingForResult):
        self.logger.debug(f"{device.name}: set_fan_direction_action for {device.address}")
        if not device.pluginProps.get("SupportsSetDirection", None):
            self.logger.warning(f"{device.name}: set_fan_direction_action: {device.address} does not support set fan direction")
            return
        msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'fan',
                    'service': 'set_direction', 'service_data': {"direction": plugin_action.props.get("direction", 0)}}
        self.send_ws(msg_data)

    def set_fan_oscillate_action(self, plugin_action, device, callerWaitingForResult):
        self.logger.debug(f"{device.name}: set_fan_oscillate_action for {device.address}")
        if not device.pluginProps.get("SupportsOscillate", None):
            self.logger.warning(f"{device.name}: set_fan_oscillate_action: {device.address} does not support oscillate")
            return
        msg_data = {"type": "call_service", "target": {"entity_id": device.address}, 'domain': 'fan',
                    'service': 'oscillate', 'service_data': {"oscillating": bool(int(plugin_action.props.get("oscillate", 0)))}}
        self.send_ws(msg_data)

    ################################################################################
    # Minimal Websocket Client
    ################################################################################
    def ws_client(self, url):
        self.logger.debug(f"Attempting connection to '{url}'")

        websocket.setdefaulttimeout(5)
        try:
            self.ws = websocket.WebSocketApp(url, on_open=self.on_open,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)
        except Exception as err:
            self.logger.error(f"Error connecting to '{url}': {err}")
            return

        self.ws.run_forever(ping_interval=50, reconnect=5)

    def on_open(self, ws):
        self.logger.debug(f"Websocket connection successful")

    def on_message(self, ws, message):
        self.logger.threaddebug(f"Websocket on_message: {message}")
        msg = json.loads(message)

        if msg['type'] == 'auth_required':
            self.logger.debug(f"Websocket got auth_required for ha_version {msg['ha_version']}, sending auth_token")
            self.ws.send(json.dumps({'type': 'auth', 'access_token': self.ha_token}))

        elif msg['type'] == 'auth_ok':
            self.logger.debug(f"Websocket got auth_ok for ha_version {msg['ha_version']}")

            # subscribe to events
            self.send_ws({"type": 'subscribe_events'})

            # get states to populate devices, and build a list of the current home assistant entities
            self.send_ws({"type": 'get_states'})

        elif msg['type'] == 'auth_invalid':
            self.logger.error(f"Websocket got auth_invalid: {msg['message']}")

        elif msg['type'] == 'result':
            if msg['id'] in self.sent_messages:
                self.logger.debug(f"Websocket reply {'Success' if msg['success'] else 'Failed'} for {self.sent_messages[msg['id']]['type']}")
                if not msg['success']:
                    self.logger.error(f"Websocket reply error: {msg['error']} for {self.sent_messages[msg['id']]}")
                else:
                    if self.sent_messages[msg['id']]['type'] == "get_states":
                        for entity in msg['result']:
                            self.logger.threaddebug(f"Got states for {entity['entity_id']}, state = {entity.get('state', None)}")
                            self.entity_update(entity['entity_id'], entity, force_update=True)
                del self.sent_messages[msg['id']]

            else:
                self.logger.debug(f"Websocket got result for unknown message id: {msg['id']}")

        elif msg.get('type', None) == 'event' and msg['event'].get('event_type', None) == 'state_changed':
            try:
                self.entity_update(msg['event']['data']['entity_id'], msg['event']['data']['new_state'])
            except Exception as e:
                self.logger.error(f"Websocket state_changed exception: {e}")
                self.logger.debug(f"Websocket state_changed:\n{msg}")

        elif msg.get('type', None) == 'event' and msg['event'].get('event_type', None) == 'lutron_caseta_button_event':
            self.logger.debug(
                f"Button event: {msg['event']['data']['serial']}: {msg['event']['data']['button_number']} {msg['event']['data']['action']}")

        elif msg.get('type', None) == 'event' and msg['event'].get('event_type', None) == 'call_service':
            data = msg['event']['data']
            self.logger.debug(
                f"call_service event: {data.get('domain', None)} {data.get('service', None)} {data.get('service_data', None).get('entity_id', None)}")

        elif msg.get('type', None) == 'event' and msg['event'].get('event_type', None) == 'automation_triggered':
            event = msg['event']
            data = event['data']
            self.logger.debug(f"automation_triggered event: {data.get('name', None)} ({data.get('entity_id', None)})")
            self.logger.threaddebug(f"{json.dumps(msg, indent=4, sort_keys=True)}")

            _update_indigo_var("event_type",   event.get('event_type', None), self.var_folder)
            _update_indigo_var("event_time",   event.get('time_fired', None), self.var_folder)
            _update_indigo_var("event_origin", event.get('origin', None), self.var_folder)
            _update_indigo_var("event_id",     data.get('entity_id', None), self.var_folder)
            _update_indigo_var("event_name",   data.get('name', None), self.var_folder)

            for trigger in indigo.triggers.iter("self"):
                if trigger.pluginTypeId == "automationEvent":
                    indigo.trigger.execute(trigger)

        # ignore these...  they are too noisy
        elif (msg.get('type', None) == 'event' and
              msg['event'].get('event_type', None) in [
                  'recorder_5min_statistics_generated',
                  'recorder_hourly_statistics_generated',
                  'lovelace_updated',
                  'device_registry_updated',
                  'entity_registry_updated',
                  'service_registered',
                  'service_removed',
                  'script_started',
                  'component_loaded',
                  'homeassistant_started',
                  'homeassistant_start',
                  'core_config_updated',
                  'config_entry_discovered',
                  'panels_updated',
                  'area_registry_updated',
                  'ios.became_active',
                  'ios.finished_launching',
                  'ios.entered_background',
                  'ios.notification_action_fired',
                  'mobile_app_notification_action',
                  'automation_reloaded',
                  'data_entry_flow_progressed',
                  'ultrasync_zone_update',
                  'insteon.button_on',
              ]):
            pass

        else:
            self.logger.warning(f"Websocket unknown message type: {json.dumps(msg)}")

    def send_ws(self, msg_data):
        self.last_sent_id += 1
        msg_data['id'] = self.last_sent_id
        self.ws.send(json.dumps(msg_data))
        self.sent_messages[self.last_sent_id] = msg_data

    def on_close(self, ws, close_status_code, close_msg):
        self.logger.debug(f"Websocket closed: {close_status_code} {close_msg}")

    def on_error(self, ws, error):
        self.logger.debug(f"Websocket error: {error}")
