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



class Plugin(indigo.PluginBase):
	########################################
	# Main Functions
	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

		self.SERVER_ADDRESS = ''
		self.SERVER_PORT = ''
		self.TOKEN = ''

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
		self.POLLINGINT = pluginPrefs.get(u'pollingInt', u'2')

		if self.debug == True:
			indigo.server.log("Home Assistant debugging enabled.")
		else:
			indigo.server.log("Home Assistant disabled.")

########################################
	def startup(self):
		self.debugLog(u"startup called")

	def shutdown(self):
		self.debugLog(u"shutdown called")

	########################################

	def deviceStartComm(self, dev):
#		self.debugLog(u"Starting device: " + dev.name)
		indigo.server.log(u"Starting device with address: " + dev.address)

		url = 'http://''%s'':''%s''/api/states/''%s' % (self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
		r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'})

		# [int(r) for r in str.split() if r.isdigit()]
		# indigo.server.log(u"Starting device with address: " + r)
		#
		# if r == 200 or r == 201:
		# 	self.logger.info("HA connection established successfully!")
		#
		# else:
		# 	self.logger.info("HA connection not established! Check your parameter settings and reload plugin")
		#


#		stateListOrDisplayStateIdChanged()

	########################################
	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		return (True, valuesDict)

	########################################
	def runConcurrentThread(self):
		try:
			while True:
				for dev in indigo.devices.iter("self"):
					store_list = []
					url = 'http://''%s'':''%s''/api/states' % (self.SERVER_ADDRESS, self.SERVER_PORT)
					r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'})

			#		device = r.json()
			#		for item in device:
			#			store_detailes = {}
			#			store_detailes[item["entity_id"]] = item["entity_id"] , item["last_updated"]
			#			store_list.append(store_detailes)
			#		self.logger.info("Print HA:\n %s \n" % (store_list[item["entity_id"]])



					if not dev.enabled or not dev.configured:
						continue

					###HA binary sensor###
					if dev.deviceTypeId == u"HAbinarySensorType":
						if dev.onState is not None:
							url = 'http://''%s'':''%s''/api/states/''%s' % (self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
							r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'})

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
						if dev.states['sensorValue'] is not None:

							url = 'http://''%s'':''%s''/api/states/''%s' % (self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
							r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'})

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
							url = 'http://''%s'':''%s''/api/states/''%s' % (self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
							r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'})

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
							url = 'http://''%s'':''%s''/api/states/''%s' % (self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
							r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'})

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


				self.sleep(3)
		except self.StopThread:
			pass	# Optionally catch the StopThread exception and do any needed cleanup.


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
