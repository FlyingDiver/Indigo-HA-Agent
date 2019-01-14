#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2016, Perceptive Automation, LLC. All rights reserved.
# http://www.indigodomo.com

import indigo

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
		indigo.server.log("Address:%s" % (url))

		r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'})

		self.logger.info("Indigo setup:%s. Status 200 or 201 connection OK!" % (r))

	########################################
	def runConcurrentThread(self):
		try:
			while True:
				for dev in indigo.devices.iter("self"):
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
					if dev.deviceTypeId == u"HAsensorType":
						if dev.sensorValue is not None:
							url = 'http://''%s'':''%s''/api/states/''%s' % (self.SERVER_ADDRESS, self.SERVER_PORT, dev.address)
							r = requests.get(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'})

							ha_device = r.json()
							self.debugLog("Device content:\n{}".format(ha_device))
#							self.logger.info("Print content:\n{}".format(ha_device))
							v=float(ha_device[u"state"])

#							self.logger.info("Indigo setup:%s" % (v))

							dev.updateStateOnServer("sensorValue", value=v, decimalPlaces=2)
							dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

						else:
							dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

					###HA switch###
					if dev.deviceTypeId == u"HAswitchType":
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
				self.sleep(2)
		except self.StopThread:
			pass	# Optionally catch the StopThread exception and do any needed cleanup.


	def actionControlDimmerRelay(self, action, dev):

		###HA switch###
		if dev.deviceTypeId == u"HAswitchType":
			###### TURN ON ######
			if action.deviceAction == indigo.kDeviceAction.TurnOn:
				# Command hardware module (dev) to turn ON here:

				url = 'http://''%s'':''%s''/api/services/switch/turn_on' % (self.SERVER_ADDRESS, self.SERVER_PORT)
				r = requests.post(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'}, data='{"entity_id": "switch.vaskerom_torketrommel"}')


				self.debugLog("Device content url:\n{}".format(url))
				self.debugLog("Device content r:\n{}".format(r))

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
				r = requests.post(url, headers={'Authorization': 'Bearer ''%s' % self.TOKEN, 'content-type': 'application/json'}, data='{"entity_id": "switch.vaskerom_torketrommel"}')


				self.debugLog("Device content url:\n{}".format(url))
				self.debugLog("Device content r:\n{}".format(r))

				sendSuccess = True		# Set to False if it failed.

				if sendSuccess:
					# If success then log that the command was successfully sent.
					indigo.server.log(u"sent \"%s\" %s" % (dev.name, "off"))

					# And then tell the Indigo Server to update the state:
					dev.updateStateOnServer("onOffState", False)
				else:
					# Else log failure but do NOT update state on Indigo Server.
					indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "off"), isError=True)


#	def closedPrefsConfigUi(self, valuesDict, userCancelled):
#		if userCancelled is False:
#			self.updatePrefs(valuesDict)
#
#		return (True, valuesDict)
