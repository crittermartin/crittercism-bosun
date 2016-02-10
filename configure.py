#!/usr/bin/python
from __future__ import print_function

import os
import sys
import json
import requests
import getpass

import cccommon

if os.path.exists("ccconfig.json"):
	sys.exit("ccconfig.json already exists; move it out of the way before proceeding.")

print("")
print("This is the config generator for the critter-bosun collector. It will generate a basic")
print("configuration for you, which you can then edit as you see fit. Note that this script")
print("will store your REST API Client ID and Crittercism username and password in the config")
print("file. You can remove them and the collector will still function using the generated OAuth2")
print("token until it expires.")
print("")
clientID = raw_input("Crittercism REST API Client ID: ")
username = raw_input("Crittercism username: ")
password = getpass.getpass("Crittercism password: ")

config = {
	"username": username,
	"password": password,
	"clientID": clientID
}

config['token'] = cccommon.authenticate(config, None)

print("")
print("Getting the list of apps...")
apps = cccommon.list_apps(config['token'])

appids = apps.keys()

for index, id in enumerate(appids):
	print("[{index}]: {appName} - {appType} (app id: {id})".format(index=index, appName=apps[id]['appName'], appType=apps[id]['appType'], id=id))

print("")
print("Type the the number for each app you want to monitor, separated by spaces (e.g., 0 3 5 6 7)")
chosenstr = raw_input("Choose which apps to monitor: ")

endpoints_limit_str = raw_input("Number of endpoints to monitor for each app [default 10]: ")
services_limit_str = raw_input("Number of services to monitor for each app [default 10]: ")

try:
	endpoints_limit = int(endpoints_limit_str)
except ValueError:
	endpoints_limit = 10

try:
	services_limit = int(services_limit_str)
except ValueError:
	services_limit = 10

config['app-info'] = cccommon.get_app_info(config['token'])

config['endpoints-auto'] = []
config['services-auto'] = []
config['transactions'] = []
config['trends'] = []

for appidxstr in chosenstr.split():
	try:
		appidx = int(appidxstr)
	except ValueError:
		print("Invalid input: {input}".format(input=appidxstr))
		continue
	
	try:
		appId = appids[appidx]
		print("Creating config entry for {name}...".format(name=apps[appId]['appName']))
		config['endpoints-auto'].append({
			"appId": appId,
			"limit": endpoints_limit
		})
		config['services-auto'].append({
			"appId": appId,
			"limit": services_limit
		})
		config['transactions'].append({
			"appId": appId,
			"token": cccommon.authenticate(config, "app/" + appId + "/transactions")
		})
		config['trends'].extend(
			[
		        {
		            "appId": appId, 
		            "groupBy": "device", 
		            "limit": 100, 
		            "sort": "userbase"
		        }, 
		        {
		            "appId": appId, 
		            "groupBy": "os", 
		            "limit": 100, 
		            "sort": "userbase"
		        }, 
		        {
		            "appId": appId, 
		            "groupBy": "appVersion", 
		            "limit": 100, 
		            "sort": "userbase"
		        }
		    ]
		)
	except IndexError:
		print("The list of apps doesn't have an item number {input}".format(input=appidx))

print("Saving configuration to ccconfig.json...")
f = open("ccconfig.json", "w")
print(json.dumps(config, indent=4, sort_keys=True), file=f)
print("Done.")
