#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2016, Perceptive Automation, LLC. All rights reserved.
# http://www.indigodomo.com

import indigo

import numbers
import os
import sys
import requests
import json
import re
import exceptions
from requests import get


################################################################################
kHvacModeEnumToStrMap = {
	indigo.kHvacMode.Cool				: u"cool",
	indigo.kHvacMode.Heat				: u"heat",
	indigo.kHvacMode.HeatCool			: u"auto",
	indigo.kHvacMode.Off				: u"off",
	indigo.kHvacMode.ProgramHeat		: u"program heat",
	indigo.kHvacMode.ProgramCool		: u"program cool",
	indigo.kHvacMode.ProgramHeatCool	: u"program auto"
}

kFanModeEnumToStrMap = {
	indigo.kFanMode.AlwaysOn			: u"always on",
	indigo.kFanMode.Auto				: u"auto"
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

		self.SERVER_ADDRESS = ''
		self.SERVER_PORT = ''
		self.TOKEN = ''

#		self.finalDict = {}
		self.SERVER_ADDRESS = u'localhost'
		self.SERVER_PORT = u'8123'
		self.TOKEN = u'1234abcd'
		self.POLLINGINT = u'2'
#		self.debug = prefs.get('HADebugInfo', False)
		indigo.devices.subscribeToChanges()

		self.updatePrefs(pluginPrefs)

	# Unload Plugin
	########################################
	def __del__(self):
		indigo.PluginBase.__del__(self)

	# Update config values
	########################################
	def updatePrefs(self, pluginPrefs):
		self.debug = pluginPrefs.get(u'HADebugInfo', False)
		self.SERVER_ADDRESS = pluginPrefs.get(u'serverAddress', u'localhost')
		self.SERVER_PORT = (pluginPrefs.get(u'serverPort', u'8123'))
		self.TOKEN = pluginPrefs.get(u'haToken', u'1234abcd')
		self.POLLINGINT = float(pluginPrefs.get("pollingInt", 3))

		if self.debug == True:
			indigo.server.log("Home Assistant debugging enabled.")
		else:
			indigo.server.log("Home Assistant debugging disabled.")

########################################
	def startup(self):
		self.debugLog(u"startup called")

	def shutdown(self):
		self.debugLog(u"shutdown called")

	########################################

	def deviceStartComm(self, dev):
#		self.debugLog(u"Starting device: " + dev.name)
		indigo.server.log(u"Starting device with address: " + dev.address)

#		url = 'http://''%s'':''%s''/api/states/''%s' % (self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
#		r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'})

		# [int(r) for r in str.split() if r.isdigit()]
		# indigo.server.log(u"Starting device with address: " + r)
		#
		# if r == 200 or r == 201:
		# 	self.logger.info("HA connection established successfully!")
		#
		# else:
		# 	self.logger.info("HA connection not established! Check your parameter settings and reload plugin")
		#

	def closedPrefsConfigUi(self, valuesDict, userCancelled):
		# Since the dialog closed we want to set the debug flag - if you don't directly use
		# a plugin's properties (and for debugLog we don't) you'll want to translate it to
		# the appropriate stuff here.
		if not userCancelled:
			self.updatePrefs(valuesDict)

#		stateListOrDisplayStateIdChanged()

	########################################
	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		return (True, valuesDict)

		########################################
# 	def getDeviceStateList(self, dev):
# 		if dev.enabled and dev.deviceTypeId == u"HAsensor":
# 			typeId = dev.deviceTypeId
# 			if typeId not in self.devicesTypeDict:
# 				return None
#
# 			defaultStatesList = self.devicesTypeDict[typeId][u'States']
# #			devProps = self.easydaq.calcNormalizedProps(dev)
#
# 			newStatesList = indigo.List()
#
# #			self.logger.info("Print content1:\n{}".format(typeId))
# #			self.logger.info("Print content2:\n{}".format(newStatesList))
# 			self.logger.info("Print content3:\n{}".format(defaultStatesList))
#
#
# 			for state in defaultStatesList:
# 				labelKey = state[u"Key"] + "test1152"
# #				if labelKey in devProps:
# 					# Found a label override in the device's property (likely set via the
# 					# device settings UI). Use the XML defined state definition, but change
# 					# the label.
# 				label = "false"
# 				state["Disabled"] = label
# #				state["hadet"] = label
# 				newStatesList.append(state)
# 				self.logger.info("Print content4:\n{}".format(newStatesList))
# 				self.logger.info("Print content5:\n{}".format(dev.pluginProps))
# #				dev.updateStateOnServer(key='volume', value=50)
# 			return newStatesList
#		if dev.enabled and dev.deviceTypeId == u"HAsensor":
#				new_props = dev.pluginProps
#				url = 'http://''%s'':''%s''/api/states/''%s' % (self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
#				r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'})

#				new_props = r.json()

#			key_value_list = [
#				{'key': 'sensorValue', 'value': 123},
#				{'key': 'someKey2', 'value': 456},
#				{'key': 'someKey3', 'value': 789.123, 'uiValue': "789.12 lbs", 'decimalPlaces': 2}
#			]

#			self.logger.info("Print content1:\n{}".format(key_value_list))

#			dev.replacePluginPropsOnServer(key_value_list)
#			dev.updateStateOnServer(key='sensorValue', value='5')
#
#		return





	########################################
	def runConcurrentThread(self):
		try:
			while True:
				for dev in indigo.devices.iter("self"):
					#					self.logger.info("Print content:\n{}".format(websoc.message))
					#					self.logger.info("Print content:\n{}".format(ha_device))
					if not dev.enabled or not dev.configured:
						continue

					###HA climate###
					if dev.deviceTypeId == u"HAclimate":
						if dev.states[u"sensorValue"] is not None:

							url = 'http://''%s'':''%s''/api/states/''%s' % (
							self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
							r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN,
														   'content-type': 'application/json'})

							ha_device = r.json()
							att = ha_device[u"attributes"]
							self.debugLog("Device content:\n{}".format(ha_device))
							#self.logger.info("Print content:\n{}".format(ha_device))
							#							self.logger.info("Indigo setup:%s" % (v))


							if ha_device[u"last_updated"] != dev.states['lastUpdated']:
								dev.updateStateOnServer("setpointHeat", value=att[u"temperature"])
								dev.updateStateOnServer("sensorValue", value=ha_device[u"state"])
								dev.updateStateOnServer("temperatureInput1", value=att[u"current_temperature"])
								dev.updateStateOnServer("current_temperature", value=att[u"current_temperature"])
								dev.updateStateOnServer("lastUpdated", value=ha_device[u"last_updated"])

	#						if dev.states["hvacOperationMode"] in [indigo.kHvacMode.Heat, indigo.kHvacMode.HeatCool, indigo.kHvacMode.ProgramHeat, indigo.kHvacMode.ProgramHeatCool]:
								if ha_device[u"state"] == 'heat':
									dev.updateStateOnServer("hvacHeaterIsOn", value=True)
								else:
									dev.updateStateOnServer("hvacHeaterIsOn", value=False)

#								self.logger.info("Print content operation_mode:\n{}".format(att[u"operation_mode"]))
								if att[u"operation_mode"] == 'heat':
									dev.updateStateOnServer("hvacOperationMode", value=1)
								else:
									dev.updateStateOnServer("hvacOperationMode", value=0)

								dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)
						else:
							dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

					###HA binary sensor###
					if dev.deviceTypeId == u"HAbinarySensorType":
						if dev.onState is not None:
							url = 'http://''%s'':''%s''/api/states/''%s' % (
							self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
							r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN,
														   'content-type': 'application/json'})

							ha_device = r.json()
							self.debugLog("Device content:\n{}".format(ha_device))
							#							self.logger.info("Print content:\n{}".format(ha_device))

							if ha_device[u"state"] == 'off':
								dev.updateStateOnServer("onOffState", value=False)
							else:
								dev.updateStateOnServer("onOffState", value=True)

							dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

						else:
							dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

					###HA sensor###
					if dev.deviceTypeId == u"HAsensor":
				#		dev.stateListOrDisplayStateIdChanged()
				#		self.logger.info("Print contentsens1:\n{}".format(dev.states))
				#		self.logger.info("Print contentsens2:\n{}".format(dev.name))
						if dev.states[u"sensorValue"] is not None:

							url = 'http://''%s'':''%s''/api/states/''%s' % (
							self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
							r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN,
														   'content-type': 'application/json'})

							ha_device = r.json()
							self.debugLog("Device content:\n{}".format(ha_device))
							#							self.logger.info("Print content:\n{}".format(ha_device))
							#							self.logger.info("Indigo setup:%s" % (v))

							if ha_device[u"last_updated"] != dev.states['lastUpdated']:
								dev.updateStateOnServer("sensorValue", value=ha_device[u"state"])
								dev.updateStateOnServer("lastUpdated", value=ha_device[u"last_updated"])
								dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

						else:
							dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

					###HA switch and dimmer###
					if dev.deviceTypeId == u"HAswitchType" or dev.deviceTypeId == u"HAdimmerType":
						if dev.onState is not None:
							url = 'http://''%s'':''%s''/api/states/''%s' % (
							self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
							r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN,
														   'content-type': 'application/json'})

							ha_device = r.json()
							self.debugLog("Device content:\n{}".format(ha_device))
							#							self.logger.info("Print content:\n{}".format(ha_device))

							if ha_device[u"state"] == 'off':
								dev.updateStateOnServer("onOffState", value=False)
							else:
								dev.updateStateOnServer("onOffState", value=True)

							dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

						else:
							dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

					if dev.deviceTypeId == u"HAdimmerType":
						if dev.brightness is not None:
							url = 'http://''%s'':''%s''/api/states/''%s' % (
							self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
							r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN,
														   'content-type': 'application/json'})

							ha_device = r.json()
							att = ha_device[u"attributes"]

							try:
								bri = att[u"brightness"] / 2.55
							except KeyError:
								bri = 0

							self.debugLog("Device content:\n{}".format(ha_device))
							#							self.logger.info("Print content:\n{}".format(bri))

							dev.updateStateOnServer("brightnessLevel", value=int(bri))

							dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

						else:
							dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

				self.sleep(self.POLLINGINT)
		except self.StopThread:
			pass  # Optionally catch the StopThread exception and do any needed cleanup.

	def actionControlDimmerRelay(self, action, dev):
		sendSuccess = False
		###HA switch###
		if dev.deviceTypeId == u"HAswitchType":
			###### TURN ON ######
			if action.deviceAction == indigo.kDeviceAction.TurnOn:
				# Command hardware module (dev) to turn ON here:

				url = 'http://''%s'':''%s''/api/services/switch/turn_on' % (self.SERVER_ADDRESS, self.SERVER_PORT)

				post_data = {"entity_id": dev.address}

				r = requests.post(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'}, data=json.dumps(post_data))

				sendSuccess = True  # Set to False if it failed.

				if sendSuccess:
					# If success then log that the command was successfully sent.
					indigo.server.log(u"sent \"%s\" %s" % (dev.name, "on"))

					# And then tell the Indigo Server to update the state.
					dev.updateStateOnServer("onOffState", True)
				else:
					# Else log failure but do NOT update state on Indigo Server.
					indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "on"), isError=True)

			###### TURN OFF ######
			elif action.deviceAction == indigo.kDimmerRelayAction.TurnOff:
				# Command hardware module (dev) to turn OFF here:
				url = 'http://''%s'':''%s''/api/services/switch/turn_off' % (self.SERVER_ADDRESS, self.SERVER_PORT)

				post_data = {"entity_id": dev.address}

				r = requests.post(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'}, data=json.dumps(post_data))

				sendSuccess = True		# Set to False if it failed.

				if sendSuccess:
					# If success then log that the command was successfully sent.
					indigo.server.log(u"sent \"%s\" %s" % (dev.name, "off"))

					# And then tell the Indigo Server to update the state:
					dev.updateStateOnServer("onOffState", False)
				else:
					# Else log failure but do NOT update state on Indigo Server.
					indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "off"), isError=True)

		###HA dimmer###
		if dev.deviceTypeId == u"HAdimmerType":
			###### TURN ON ######
			if action.deviceAction == indigo.kDeviceAction.TurnOn:
				# Command hardware module (dev) to turn ON here:

				url = 'http://''%s'':''%s''/api/services/light/turn_on' % (self.SERVER_ADDRESS, self.SERVER_PORT)

				post_data = {"entity_id": dev.address}

				r = requests.post(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'}, data=json.dumps(post_data))

				sendSuccess = True  # Set to False if it failed.

				if sendSuccess:
					# If success then log that the command was successfully sent.
					indigo.server.log(u"sent \"%s\" %s" % (dev.name, "on"))

					# And then tell the Indigo Server to update the state.
					dev.updateStateOnServer("onOffState", True)
				else:
					# Else log failure but do NOT update state on Indigo Server.
					indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "on"), isError=True)

			###### TURN OFF ######
			elif action.deviceAction == indigo.kDimmerRelayAction.TurnOff:
				# Command hardware module (dev) to turn OFF here:
				url = 'http://''%s'':''%s''/api/services/light/turn_off' % (self.SERVER_ADDRESS, self.SERVER_PORT)

				post_data = {"entity_id": dev.address}

				r = requests.post(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'}, data=json.dumps(post_data))

				sendSuccess = True		# Set to False if it failed.

				if sendSuccess:
					# If success then log that the command was successfully sent.
					indigo.server.log(u"sent \"%s\" %s" % (dev.name, "off"))

					# And then tell the Indigo Server to update the state:
					dev.updateStateOnServer("onOffState", False)
				else:
					# Else log failure but do NOT update state on Indigo Server.
					indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "off"), isError=True)

			###### SET BRIGHTNESS ######
			elif action.deviceAction == indigo.kDimmerRelayAction.SetBrightness:
				# Command hardware module (dev) to turn OFF here:
				url = 'http://''%s'':''%s''/api/services/light/turn_on' % (self.SERVER_ADDRESS, self.SERVER_PORT)

				newBrightness = action.actionValue
				post_data = {"entity_id": dev.address, "brightness_pct": newBrightness}
				data = data=json.dumps(post_data)

				indigo.server.log(u"JSON data:" + data)
				r = requests.post(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'}, data=data)

				sendSuccess = True		# Set to False if it failed.

				if sendSuccess:
					# If success then log that the command was successfully sent.
					indigo.server.log(u"sent \"%s\" %s" % (dev.name, newBrightness))

					# And then tell the Indigo Server to update the state:
					dev.updateStateOnServer("brightnessLevel", newBrightness)
				else:
					# Else log failure but do NOT update state on Indigo Server.
					indigo.server.log(u"send \"%s\" %s failed" % (dev.name, dev.brightness), isError=True)



	########################################
	# Thermostat Action callback
	######################
	# Main thermostat action bottleneck called by Indigo Server.
	def actionControlThermostat(self, action, dev):
		###### SET HVAC MODE ######
		if action.thermostatAction == indigo.kThermostatAction.SetHvacMode:
			self._handleChangeHvacModeAction(dev, action.actionMode)

		###### SET FAN MODE ######
		elif action.thermostatAction == indigo.kThermostatAction.SetFanMode:
			self._handleChangeFanModeAction(dev, action.actionMode)

		###### SET COOL SETPOINT ######
		elif action.thermostatAction == indigo.kThermostatAction.SetCoolSetpoint:
			newSetpoint = action.actionValue
			self._handleChangeSetpointAction(dev, newSetpoint, u"change cool setpoint", u"setpointCool")

		###### SET HEAT SETPOINT ######
		elif action.thermostatAction == indigo.kThermostatAction.SetHeatSetpoint:
			newSetpoint = action.actionValue
			self._handleChangeSetpointAction(dev, newSetpoint, u"change heat setpoint", u"setpointHeat")

		###### DECREASE/INCREASE COOL SETPOINT ######
		elif action.thermostatAction == indigo.kThermostatAction.DecreaseCoolSetpoint:
			newSetpoint = dev.coolSetpoint - action.actionValue
			self._handleChangeSetpointAction(dev, newSetpoint, u"decrease cool setpoint", u"setpointCool")

		elif action.thermostatAction == indigo.kThermostatAction.IncreaseCoolSetpoint:
			newSetpoint = dev.coolSetpoint + action.actionValue
			self._handleChangeSetpointAction(dev, newSetpoint, u"increase cool setpoint", u"setpointCool")

		###### DECREASE/INCREASE HEAT SETPOINT ######
		elif action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint:
			newSetpoint = dev.heatSetpoint - action.actionValue
			self._handleChangeSetpointAction(dev, newSetpoint, u"decrease heat setpoint", u"setpointHeat")

		elif action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint:
			newSetpoint = dev.heatSetpoint + action.actionValue
			self._handleChangeSetpointAction(dev, newSetpoint, u"increase heat setpoint", u"setpointHeat")

#		###### REQUEST STATE UPDATES ######
#		elif action.thermostatAction in [indigo.kThermostatAction.RequestStatusAll, indigo.kThermostatAction.RequestMode,
#		indigo.kThermostatAction.RequestEquipmentState, indigo.kThermostatAction.RequestTemperatures, indigo.kThermostatAction.RequestHumidities,
#		indigo.kThermostatAction.RequestDeadbands, indigo.kThermostatAction.RequestSetpoints]:
#			self._refreshStatesFromHardware(dev, True, False)

	########################################

	######################
	# Process action request from Indigo Server to change main thermostat's main mode.
	def _handleChangeHvacModeAction(self, dev, newHvacMode):

		if newHvacMode == 0:
			newHvacModeHA = 'off'
		else:
			newHvacModeHA = 'heat'


		url = 'http://''%s'':''%s''/api/services/climate/set_operation_mode' % (self.SERVER_ADDRESS, self.SERVER_PORT)

		self.logger.info("Print content newHVACmode:\n{}".format(newHvacModeHA))

		post_data = {"entity_id": dev.address, "operation_mode": newHvacModeHA}
		data = data=json.dumps(post_data)

		indigo.server.log(u"JSON data:" + data)
		r = requests.post(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'}, data=data)

		sendSuccess = True		# Set to False if it failed.

		actionStr = _lookupActionStrFromHvacMode(newHvacMode)
		if sendSuccess:
			# If success then log that the command was successfully sent.
			indigo.server.log(u"sent \"%s\" mode change to %s" % (dev.name, actionStr))

			# And then tell the Indigo Server to update the state.
			if "hvacOperationMode" in dev.states:
				dev.updateStateOnServer("hvacOperationMode", newHvacMode)
		else:
			# Else log failure but do NOT update state on Indigo Server.
			indigo.server.log(u"send \"%s\" mode change to %s failed" % (dev.name, actionStr), isError=True)



	######################
	# Process action request from Indigo Server to change a cool/heat setpoint.
	def _handleChangeSetpointAction(self, dev, newSetpoint, logActionName, stateKey):
		url = 'http://''%s'':''%s''/api/states/''%s' % (
		self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
		r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN,'content-type': 'application/json'})

		ha_device = r.json()
		att = ha_device[u"attributes"]
		SetpointMaxHA = att[u"max_temp"]
		SetpointMinHA = att[u"min_temp"]

		if newSetpoint < SetpointMinHA:
			newSetpoint = SetpointMinHA		# Arbitrary -- set to whatever hardware minimum setpoint value is.
		elif newSetpoint > SetpointMaxHA:
			newSetpoint = SetpointMaxHA		# Arbitrary -- set to whatever hardware maximum setpoint value is.

		sendSuccess = False

		if stateKey == u"setpointCool":
			# Command hardware module (dev) to change the cool setpoint to newSetpoint here:
			# ** IMPLEMENT ME **
			sendSuccess = True			# Set to False if it failed.
		elif stateKey == u"setpointHeat":
			url = 'http://''%s'':''%s''/api/services/climate/set_temperature' % (self.SERVER_ADDRESS, self.SERVER_PORT)

			post_data = {"entity_id": dev.address, "temperature": newSetpoint}
			data = data=json.dumps(post_data)

			indigo.server.log(u"JSON data:" + data)
			r = requests.post(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'}, data=data)

			sendSuccess = True			# Set to False if it failed.

		if sendSuccess:
			# If success then log that the command was successfully sent.
			indigo.server.log(u"sent \"%s\" %s to %.1f°" % (dev.name, logActionName, newSetpoint))

			# And then tell the Indigo Server to update the state.
			if stateKey in dev.states:
				dev.updateStateOnServer(stateKey, float(newSetpoint), uiValue="%.1f °F" % (newSetpoint))
		else:
			# Else log failure but do NOT update state on Indigo Server.
			indigo.server.log(u"send \"%s\" %s to %.1f° failed" % (dev.name, logActionName, newSetpoint), isError=True)
