#! /usr/bin/env python
# -*- coding: utf-8 -*-

import indigo
import requests
import logging

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
    # Main Functions
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)
        self.logLevel = int(self.pluginPrefs.get("logLevel", logging.INFO))
        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.debug(f"logLevel = {self.logLevel}")

        self.server_address = 'localhost'
        self.server_port = '8123'
        self.ha_token = ''
        self.poll_interval = '2'
        self.updatePrefs(pluginPrefs)

    # Update config values
    ########################################
    def updatePrefs(self, pluginPrefs):
        self.server_address = pluginPrefs.get('serverAddress', 'localhost')
        self.server_port = (pluginPrefs.get('serverPort', '8123'))
        self.ha_token = pluginPrefs.get('haToken', '')
        self.poll_interval = float(pluginPrefs.get("pollingInt", 3))
        self.logLevel = int(pluginPrefs.get("logLevel", logging.INFO))
        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.debug(f"logLevel = {self.logLevel}")

    ########################################
    def startup(self):
        self.logger.debug("startup called")
        indigo.devices.subscribeToChanges()

    def shutdown(self):
        self.logger.debug("shutdown called")

    ########################################

    def deviceStartComm(self, device):
        self.logger.info(f"{device.name}: Starting device with address: {device.address}")
        device.stateListOrDisplayStateIdChanged()

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self.updatePrefs(valuesDict)

    ########################################
    def runConcurrentThread(self):

        headers = {'Authorization': f'Bearer {self.ha_token}', 'content-type': 'application/json'}
        try:
            while True:
                for device in indigo.devices.iter("self"):

                    if not device.enabled or not device.configured:
                        continue

                    url = f"http://{self.server_address}:{self.server_port}/api/states/{device.address}"   # noqa
                    ha_device = requests.get(url, headers=headers).json()
                    att = ha_device.get("attributes", None)
                    if not att:
                        self.logger.error(f"Device {device.name} no attributes returned")
                        continue
                        
                    if device.deviceTypeId == "HAclimate":

                        if ha_device["last_updated"] != device.states['lastUpdated']:
                            self.logger.threaddebug(f"{device.name} content:\n{ha_device}")
                            update_list = [
                                {'key': "setpointHeat", 'value': att["temperature"]},
                                {'key': "hvacOperationMode", 'value': kHvacModeStrToEnumMap[ha_device["state"]]},
                                {'key': "temperatureInput1", 'value': att["current_temperature"]},
                                {'key': "lastUpdated", 'value': ha_device["last_updated"]},
                            ]
                            device.updateStatesOnServer(update_list)
                            device.updateStateImageOnServer(indigo.kStateImageSel.Auto)

                    elif device.deviceTypeId == "HAbinarySensorType":
                        if ha_device["last_updated"] != device.states['lastUpdated']:
                            self.logger.threaddebug(f"{device.name} content:\n{ha_device}")
                            if ha_device["state"] == 'off':
                                device.updateStateOnServer("onOffState", value=False)
                            else:
                                device.updateStateOnServer("onOffState", value=True)
                            device.updateStateOnServer("lastUpdated", value=ha_device["last_updated"])
                            device.updateStateImageOnServer(indigo.kStateImageSel.Auto)

                    elif device.deviceTypeId == "HAsensor":
                        if ha_device["last_updated"] != device.states['lastUpdated']:
                            self.logger.threaddebug(f"{device.name} content:\n{ha_device}")
                            device.updateStateOnServer("sensorValue", value=ha_device["state"])
                            device.updateStateOnServer("lastUpdated", value=ha_device["last_updated"])
                            device.updateStateImageOnServer(indigo.kStateImageSel.Auto)

                    elif device.deviceTypeId == "HAswitchType":
                        if ha_device["last_updated"] != device.states['lastUpdated']:
                            self.logger.threaddebug(f"{device.name} content:\n{ha_device}")
                            if ha_device["state"] == 'off':
                                device.updateStateOnServer("onOffState", value=False)
                            else:
                                device.updateStateOnServer("onOffState", value=True)
                            device.updateStateImageOnServer(indigo.kStateImageSel.Auto)

                    elif device.deviceTypeId == "HAdimmerType":
                        if ha_device["last_updated"] != device.states['lastUpdated']:
                            self.logger.threaddebug(f"{device.name} content:\n{ha_device}")
                            if ha_device["state"] == 'off':
                                device.updateStateOnServer("onOffState", value=False)
                            else:
                                device.updateStateOnServer("onOffState", value=True)
                                brightness = att.get("brightness", 0) / 2.55
                                device.updateStateOnServer("brightnessLevel", value=round(brightness))
                            device.updateStateImageOnServer(indigo.kStateImageSel.Auto)

                    else:
                        self.logger.error(f"{device.name}: Unknown device type: {device.deviceTypeId}")

                self.sleep(self.poll_interval)

        except self.StopThread:
            pass

    ########################################
    # Relay/Dimmer Action methods
    ########################################
    def actionControlDimmerRelay(self, action, dev):
        headers = {'Authorization': f'Bearer {self.ha_token}', 'content-type': 'application/json'}
        post_data = {"entity_id": dev.address}
        self.logger.debug(f"{dev.name}: sending {action.deviceAction} to {dev.address}")

        if dev.deviceTypeId == "HAswitchType":
            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                url = f"http://{self.server_address}:{self.server_port}/api/services/switch/turn_on"    # noqa
                r = requests.post(url, headers=headers,json=post_data)

            elif action.deviceAction == indigo.kDimmerRelayAction.TurnOff:
                url = f"http://{self.server_address}:{self.server_port}/api/services/switch/turn_off"   # noqa
                r = requests.post(url, headers=headers,json=post_data)

        if dev.deviceTypeId == "HAdimmerType":
            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                url = f"http://{self.server_address}:{self.server_port}/api/services/light/turn_on" # noqa
                r = requests.post(url, headers=headers,json=post_data)

            elif action.deviceAction == indigo.kDimmerRelayAction.TurnOff:
                url = f"http://{self.server_address}:{self.server_port}/api/services/light/turn_off"    # noqa
                r = requests.post(url, headers=headers,json=post_data)

            elif action.deviceAction == indigo.kDimmerRelayAction.SetBrightness:

                url = f"http://{self.server_address}:{self.server_port}/api/services/light/turn_on"   # noqa
                post_data = {"entity_id": dev.address, "brightness_pct": action.actionValue}
                r = requests.post(url, headers=headers,json=post_data)

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
            self._handleChangeSetpointAction(dev, newSetpoint,"decrease cool setpoint", "setpointCool")

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

        url = f"http://{self.server_address}:{self.server_port}/api/services/climate/set_operation_mode"    # noqa
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

        url = f"http://{self.server_address}:{self.server_port}/api/states/{dev.address}"   # noqa
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
            url = f"http://{self.server_address}:{self.server_port}/api/services/climate/set_temperature"   # noqa
            newHvacModeHA = action.actionValue
            post_data = {"entity_id": dev.address, "temperature": newSetpoint}
            r = requests.post(url, headers=headers, json=post_data)
            self.logger.debug(f"sent \"{dev.name}\" {logActionName} to {newSetpoint:.1f}°")

        if stateKey in dev.states:
            dev.updateStateOnServer(stateKey, float(newSetpoint), uiValue=f"{newSetpoint:.1f} °F")
