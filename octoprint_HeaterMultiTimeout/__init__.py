#
# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# coding=utf-8

from __future__ import absolute_import
import time

import octoprint.plugin
from octoprint.util import RepeatedTimer


class HeaterMultiTimeout(octoprint.plugin.AssetPlugin,
					octoprint.plugin.SettingsPlugin,
					octoprint.plugin.ShutdownPlugin,
					octoprint.plugin.StartupPlugin,
					octoprint.plugin.TemplatePlugin):

	def __init__(self):
		self._checkTempTimer = None
		self._heaterTimer = None

	def _restartTimer(self):
		# stop the timer
		if self._checkTempTimer:
			self._logger.debug(u"Stopping RepeatedTimer...")
			self._checkTempTimer.cancel()
			self._checkTempTimer = None

		interval = self._settings.get_int(['interval'])
		if self._settings.get_boolean(['enabled']) and interval:
			self._logger.debug(u"Starting RepeatedTimer...")
			self._checkTempTimer = RepeatedTimer(interval, self.CheckTimer, None, None, True)
			self._checkTempTimer.start()

	def CheckTimer(self):
		temps = self._printer.get_current_temperatures()
		self._logger.debug(u"CheckTemps(): timer: %r, temps: %r" % (self._heaterTimer, temps))
		if not temps:
			self._heaterTimer = None
			return

		if self._printer.is_printing():
			if self._heaterTimer:
				self._logger.info(u"Print started, timer stopped")
				self._heaterTimer = None
		else:
			heaters_on = False
			# find out if any of the heaters are on
			for k in temps.keys():
				if temps[k]['target']:
					heaters_on = True
					break

			if heaters_on:
				if not self._heaterTimer:
					self._heaterTimer = int(time.time())
					self._logger.info(u"Timer Started: %r" % self._heaterTimer)
				elif time.time() - self._heaterTimer > self._settings.get_int(['timeout']) and self._printer.is_ready():
					self._logger.info(u"Heater Timeout triggered, shutting down heaters")
					if self._settings.get_int(['notifications']):
						self._plugin_manager.send_plugin_message(__plugin_name__, dict(type="popup", msg="Heater Idle Timeout Triggered"))
					for k in temps.keys():
						if temps[k]['target']:
							self._printer.set_temperature(k, 0)
				elif time.time() - self._heaterTimer > self._settings.get_int(['pausetimeout']) and self._printer.is_paused():
					self._logger.info(u"Pause Heater Timeout triggered, shutting down heaters")
					if self._settings.get_int(['notifications']):
						self._plugin_manager.send_plugin_message(__plugin_name__, dict(type="popup", msg="Heater Pause Idle Timeout Triggered"))
					for k in temps.keys():
						if temps[k]['target']:
							self._printer.set_temperature(k, 0)
				elif time.time() - self._heaterTimer > self._settings.get_int(['fallbacktimeout']) and not self._printer.is_paused():
					self._logger.info(u"Fallback Heater Timeout triggered, shutting down heaters")
					if self._settings.get_int(['notifications']):
						self._plugin_manager.send_plugin_message(__plugin_name__, dict(type="popup", msg="Heater Fallback Idle Timeout Triggered"))
					for k in temps.keys():
						if temps[k]['target']:
							self._printer.set_temperature(k, 0)
			else:
				if self._heaterTimer:
					self._logger.info(u"Timer Stopped")
					self._heaterTimer = None

	##-- StartupPlugin hooks

	def on_after_startup(self):
		self._logger.info(u"Starting up...")
		self._restartTimer()

	##-- ShutdownPlugin hooks

	def on_shutdown(self):
		self._logger.info(u"Shutting down...")

	##-- AssetPlugin hooks

	def get_assets(self):
		return dict(js=["js/HeaterMultiTimeout.js"])

	##~~ SettingsPlugin mixin

	def get_settings_version(self):
		return 2

	def get_template_configs(self):
		return [
			dict(type="settings", name="Heater Multi Timeout", custom_bindings=False)
		]

	def get_settings_defaults(self):
		return dict(
			enabled=False,
			notifications=True,
			interval=15,
			timeout=360,
			pausetimeout=18000,
			fallbacktimeout=900
		)

	def on_settings_initialized(self):
		self._logger.debug(u"HeaterMultiTimeout on_settings_initialized()")
		self._restartTimer()

	def on_settings_save(self, data):
		# make sure we don't get negative values
		for k in ('interval', 'timeout'):
			if data.get(k): data[k] = max(0, int(data[k]))
		self._logger.debug(u"HeaterMultiTimeout on_settings_save(%r)" % (data,))

		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
		self._restartTimer()

	##~~ Softwareupdate hook

	def get_update_information(self):
		return dict(
			HeaterMultiTimeout=dict(
				displayName="Heater Multi Timeout Plugin",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="netinetwalker",
				repo="OctoPrint-HeaterMultiTimeout",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/netinetwalker/OctoPrint-HeaterMultiTimeout/archive/{target_version}.zip"
			)
		)


__plugin_name__ = "HeaterMultiTimeout"
__plugin_pythoncompat__ = ">=2.7,<4"


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = HeaterMultiTimeout()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
	}
