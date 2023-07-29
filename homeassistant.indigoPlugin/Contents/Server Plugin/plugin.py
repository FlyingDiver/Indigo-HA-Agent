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

kFanModeEnumToStrMap = {
    indigo.kFanMode.AlwaysOn: "always on",
    indigo.kFanMode.Auto: "auto"
}

def _lookupActionStrFromHvacMode(hvacMode):
    return kHvacModeEnumToStrMap.get(hvacMode, u"unknown")

def _lookupActionStrFromFanMode(fanMode):
    return kFanModeEnumToStrMap.get(fanMode, u"unknown")

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

        self.SERVER_ADDRESS = 'localhost'
        self.SERVER_PORT = '8123'
        self.TOKEN = '1234abcd'
        self.POLLINGINT = '2'
        self.updatePrefs(pluginPrefs)

    # Update config values
    ########################################
    def updatePrefs(self, pluginPrefs):
        self.SERVER_ADDRESS = pluginPrefs.get('serverAddress', 'localhost')
        self.SERVER_PORT = (pluginPrefs.get('serverPort', '8123'))
        self.TOKEN = pluginPrefs.get('haToken', '1234abcd')
        self.POLLINGINT = float(pluginPrefs.get("pollingInt", 3))
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

    def deviceStartComm(self, dev):
        self.logger.info(f"Starting device with address: {dev.address}")

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self.updatePrefs(valuesDict)

    ########################################
    def runConcurrentThread(self):

        headers = {'Authorization': f'Bearer {self.TOKEN}', 'content-type': 'application/json'}
        try:
            while True:
                for dev in indigo.devices.iter("self"):

                    if not dev.enabled or not dev.configured:
                        continue

                    url = f"http://{self.SERVER_ADDRESS}:{self.SERVER_PORT}/api/states/{dev.address}"   # noqa
                    ha_device = requests.get(url, headers=headers).json()
                    self.logger.threaddebug(f"Device content:\n{ha_device}")
                    att = ha_device.get("attributes", None)
                    if not att:
                        self.logger.error(f"Device {dev.name} no attributes returned")
                        continue
                        
                    if dev.deviceTypeId == "HAclimate":
                        if dev.states["sensorValue"] is not None:

                            if ha_device["last_updated"] != dev.states['lastUpdated']:
                                dev.updateStateOnServer("setpointHeat", value=att["temperature"])
                                dev.updateStateOnServer("sensorValue", value=ha_device["state"])
                                dev.updateStateOnServer("temperatureInput1", value=att["current_temperature"])
                                dev.updateStateOnServer("current_temperature", value=att["current_temperature"])
                                dev.updateStateOnServer("lastUpdated", value=ha_device["last_updated"])

                                if ha_device["state"] == 'heat':
                                    dev.updateStateOnServer("hvacHeaterIsOn", value=True)
                                else:
                                    dev.updateStateOnServer("hvacHeaterIsOn", value=False)

                                if att["operation_mode"] == 'heat':
                                    dev.updateStateOnServer("hvacOperationMode", value=1)
                                else:
                                    dev.updateStateOnServer("hvacOperationMode", value=0)

                                dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)
                        else:
                            dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

                    if dev.deviceTypeId == "HAbinarySensorType":
                        if dev.onState:
                            if ha_device["state"] == 'off':
                                dev.updateStateOnServer("onOffState", value=False)
                            else:
                                dev.updateStateOnServer("onOffState", value=True)
                        dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

                    if dev.deviceTypeId == "HAsensor":
                        if dev.states[u"sensorValue"] is not None:
                            if ha_device[u"last_updated"] != dev.states['lastUpdated']:
                                dev.updateStateOnServer("sensorValue", value=ha_device[u"state"])
                                dev.updateStateOnServer("lastUpdated", value=ha_device[u"last_updated"])
                        dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

                    if dev.deviceTypeId == "HAswitchType" or dev.deviceTypeId == "HAdimmerType":
                        if dev.onState is not None:

                            if ha_device[u"state"] == 'off':
                                dev.updateStateOnServer("onOffState", value=False)
                            else:
                                dev.updateStateOnServer("onOffState", value=True)

                        dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

                    if dev.deviceTypeId == "HAdimmerType":
                        if dev.brightness is not None:
                            try:
                                bri = att["brightness"] / 2.55
                            except KeyError:
                                bri = 0

                            dev.updateStateOnServer("brightnessLevel", value=int(bri))
                        dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

                self.sleep(self.POLLINGINT)

        except self.StopThread:
            pass

    ########################################
    # Relay/Dimmer Action methods
    ########################################
    def actionControlDimmerRelay(self, action, dev):
        headers = {'Authorization': f'Bearer {self.TOKEN}', 'content-type': 'application/json'}
        sendSuccess = False
        if dev.deviceTypeId == "HAswitchType":
            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                url = f"http://{self.SERVER_ADDRESS}:{self.SERVER_PORT}/api/services/switch/turn_on"    # noqa
                post_data = {"entity_id": dev.address}
                r = requests.post(url, headers=headers,json=post_data)

                self.logger.debug(f"sent \"{dev.name}\" on")
                dev.updateStateOnServer("onOffState", True)

            elif action.deviceAction == indigo.kDimmerRelayAction.TurnOff:
                url = f"http://{self.SERVER_ADDRESS}:{self.SERVER_PORT}/api/services/switch/turn_off"   # noqa
                post_data = {"entity_id": dev.address}
                r = requests.post(url, headers=headers,json=post_data)

                self.logger.debug(f"sent \"{dev.name}\" off")
                dev.updateStateOnServer("onOffState", True)

        if dev.deviceTypeId == "HAdimmerType":

            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                url = f"http://{self.SERVER_ADDRESS}:{self.SERVER_PORT}/api/services/light/turn_on" # noqa
                post_data = {"entity_id": dev.address}
                r = requests.post(url, headers=headers,json=post_data)

                self.logger.debug(f"sent \"{dev.name}\" on")
                dev.updateStateOnServer("onOffState", True)

            elif action.deviceAction == indigo.kDimmerRelayAction.TurnOff:

                url = f"http://{self.SERVER_ADDRESS}:{self.SERVER_PORT}/api/services/light/turn_off"    # noqa
                post_data = {"entity_id": dev.address}
                r = requests.post(url, headers=headers,json=post_data)

                self.logger.debug(f"sent \"{dev.name}\" off")
                dev.updateStateOnServer("onOffState", True)

            elif action.deviceAction == indigo.kDimmerRelayAction.SetBrightness:

                url = f"http://{self.SERVER_ADDRESS}:{self.SERVER_PORT}/api/services/light/turn_on"   # noqa
                newBrightness = action.actionValue
                post_data = {"entity_id": dev.address, "brightness_pct": newBrightness}
                r = requests.post(url, headers=headers,json=post_data)

                self.logger.debug(f"sent \"{dev.name}\" set brightness to {newBrightness}")
                dev.updateStateOnServer("onOffState", True)

    ########################################
    # Thermostat Action methods
    ########################################
    def actionControlThermostat(self, action, dev):
        headers = {'Authorization': f'Bearer {self.TOKEN}', 'content-type': 'application/json'}
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
        headers = {'Authorization': f'Bearer {self.TOKEN}', 'content-type': 'application/json'}

        if newHvacMode == 0:
            newHvacModeHA = 'off'
        else:
            newHvacModeHA = 'heat'
        self.logger.info(f"newHVACmode: {newHvacModeHA}")

        url = f"http://{self.SERVER_ADDRESS}:{self.SERVER_PORT}/api/services/climate/set_operation_mode"    # noqa
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
        headers = {'Authorization': f'Bearer {self.TOKEN}', 'content-type': 'application/json'}

        url = f"http://{self.SERVER_ADDRESS}:{self.SERVER_PORT}/api/states/{dev.address}"   # noqa
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
            url = f"http://{self.SERVER_ADDRESS}:{self.SERVER_PORT}/api/services/climate/set_temperature"   # noqa
            newHvacModeHA = action.actionValue
            post_data = {"entity_id": dev.address, "temperature": newSetpoint}
            r = requests.post(url, headers=headers, json=post_data)
            self.logger.debug(f"sent \"{dev.name}\" {logActionName} to {newSetpoint:.1f}°")

        if stateKey in dev.states:
            dev.updateStateOnServer(stateKey, float(newSetpoint), uiValue=f"{newSetpoint:.1f} °F")
