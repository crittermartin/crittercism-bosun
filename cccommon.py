from __future__ import print_function

import os
import re
import sys
import base64
import requests
import json
import time
import datetime
import dateutil.parser


def initialize():
	exepath = os.path.abspath(os.path.dirname(sys.argv[0]))

	CONFIG_FILE_NAMES = [
		'./ccconfig.json',
		exepath + '/ccconfig.json',
		exepath + '/../ccconfig.json',
		exepath + '/../../ccconfig.json',
		exepath + '/../etc/ccconfig.json',
		'/etc/ccconfig.json'
	]
	
	if 'CCCONFIG' in os.environ:
		CONFIG_FILE_NAMES.insert(0, os.environ['CCCONFIG'])
	
	i = 0
	config_file = None
	while not config_file:
		try:
			config_file = open(CONFIG_FILE_NAMES[i], "r+")
			config = json.load(config_file)
		except IndexError:
			sys.exit("No valid configurations found in {list}".format(list=json.dumps(CONFIG_FILE_NAMES, indent=2)))
		except IOError as e:
			i += 1
	
	return (config, config_file)

def authenticate(config, scope):
	if not 'username' in config or not 'password' in config or not 'clientID' in config:
		return None

	params = {
				"username": config['username'],
				"password": config['password'],
				"grant_type": "password",
			}

	if scope:
		params['scope'] = scope

	try:
		authstr = "Basic "	 + base64.b64encode(config['clientID'] + ":ANYTHING")
		response = requests.post(
			url="https://developers.crittercism.com/v1.0/token",
			params=params,
			headers={
				"Authorization": authstr,
			},
		)
		response_object = json.loads(response.content)
		return response_object['access_token']
	except requests.exceptions.RequestException:
		print('HTTP Request failed', file=sys.stderr)
		return None

def list_apps(token):
	try:
		response = requests.get(
			url="https://developers.crittercism.com/v1.0/apps",
			params={
				"attributes": "appName,appType",
			},
			headers={
				"Authorization": "Bearer " + token
			}
		)
		
		if response.status_code != 200:
			sys.exit("Got HTTP status {code} trying to list apps".format(code=response.status_code))
	
		return json.loads(response.content)
	
	except requests.exceptions.RequestException:
		print('HTTP Request failed', file=sys.stderr)
		return None

def get_app_info(token):
	apps = list_apps(token)
	
	if not apps:
		return None
	
	app_info = {}
	for id, info in apps.iteritems():
		app_info[id] = {
			"appName": info['appName'],
			"appType": info['appType']
		}
	return app_info

def check_token(token):

	try:
		response = requests.get(
			url="https://developers.crittercism.com:443/v1.0/apps",
			params={
				"attributes": "appName",
			},
			headers={
				"Authorization": "Bearer " + token,
			},
		)
		if response.status_code == 200:
			return True
		else:
			return False
	except requests.exceptions.RequestException:
		return False

def check_tx_token(token, appId):

	try:
		response = requests.get(
			url="https://txn-report.crittercism.com/v1.0/" + appId + "/summary",
			headers={
				"Authorization": "Bearer " + token,
			},
		)
		if response.status_code == 200:
			return True
		else:
			return False
	except requests.exceptions.RequestException:
		return False

def check_txn_api_response(response):
	if response.status_code != 200:
		return (False, "HTTP status {code}".format(code=response.status_code))

	if not response.content:
		return (False, "Response has no content")

	data = json.loads(response.content)
	
	if not 'series' in data:
		return (False, "Response data contains no series")

	return (True, data)

def check_apm_api_response(response):
	if response.status_code != 200:
		return (False, "HTTP status {code}".format(code=response.status_code))

	if not response.content:
		return (False, "Response has no content")

	data = json.loads(response.content)
	
	if not 'data' in data:
		return (False, "Response has no data element")

	if not 'series' in data['data']:
		return (False, "Response data contains no series")

	return (True, data)

def clean_for_opentsdb(name):
	return re.sub(r'[^a-zA-Z0-9\-_\.\/]', '-', name)
