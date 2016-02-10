#!/usr/bin/python
from __future__ import print_function

import os
import signal
import re
import sys
import base64
import requests
import grequests
import json
import time
import datetime
import dateutil.parser
import threading
import urllib

exepath = os.path.abspath(os.path.dirname(sys.argv[0]))
sys.path.append(exepath)
sys.path.append(exepath + '/..')
sys.path.append(exepath + '/../..')
sys.path.append(exepath + '/../etc')

import cccommon

SCRIPT_TIMEOUT = 900
MAX_CONCURRENT_API_CALLS = 50

def get_txn_names(token, appId):

	try:
		response = requests.get(
			url="https://txn-report.crittercism.com/v1.0/" + appId + "/details/change",
			headers={
				"Authorization": "Bearer " + token,
			},
			params={
				 "pageSize": "1000",
			},
		)
		if response.status_code != 200:
			return None

		response_object = json.loads(response.content)
		tx_names = []
		for tx_group in response_object['groups']:
			tx_names.append(tx_group['name'])
		return tx_names

	except requests.exceptions.RequestException:
		return None

def get_txn_data(token, appId):
	rs = []

	txn_names = get_txn_names(token, appId)
	
	my_stats["transactions.configured"] += len(txn_names)

	for group in txn_names:
		r = grequests.get(
			url="https://txn-report.crittercism.com/v1.0/" + appId + "/group/" + group + "/trends/PT1H",
			headers={
				"Authorization": "Bearer " + token,
			},
		)
		rs.append(r)

	my_stats["rest-api-requests"] += len(rs)
	print("{me}: Sending {count} graph requests to Crittercism".format(me=me, count=len(rs)), file=sys.stderr)

	responses = grequests.map(rs, size=MAX_CONCURRENT_API_CALLS)
	for response in responses:
		(ok, data) = cccommon.check_txn_api_response(response)
		if not ok:
			my_stats["rest-api-failures"] += 1
			url = "unknown URL"
			if response and response.request and response.request.url:
				url = response.request.url
			print("{me}: {error} for {url}".format(me=me, error=data, url=url), file=sys.stderr)
			continue
			
		my_stats["rest-api-responses"] += 1
		
		url = urllib.unquote(response.request.url)
		urlelements = url.split('/')
		clean_group_name = re.sub(r'\W', '-', urlelements[6])

		for name, series in data['series'].iteritems():
			if not 'buckets' in series:
				print('{me}: Series {name} has no buckets for transaction "{txn}"'.format(me=me, name=name, txn=group), file=sys.stderr)
				continue
	
			for item in series['buckets']:
				start = dateutil.parser.parse(item['start'])
				outcome = name
				if outcome == "all":
					outcome = "volume"
				metric = "crittercism.transactions.{outcome}".format(outcome=outcome)
				tags = basic_tags_for_app(appId)
				tags += " name={name}".format(name=clean_group_name)
				my_stats["data-points-collected"] += 1
				print("{metric} {ts} {value} {tags}".format(metric=metric, ts=int(time.mktime(start.timetuple())), value=item['value'], tags=tags))

def basic_tags_for_app(appId):
	tags = "appId={appId}".format(appId=appId)
	if 'app-info' in config and appId in config['app-info']:
		appName = cccommon.clean_for_opentsdb(config['app-info'][appId]['appName'])
		appType = cccommon.clean_for_opentsdb(config['app-info'][appId]['appType'])
		tags += " appName={appName} appType={appType}".format(appName=appName, appType=appType)
	return tags

def time_expired():
	print("{me}: Timeout expired! Exiting.".format(me=me), file=sys.stderr)
	os._exit(1)

def handle_sigint(signum, frame):
	# this is just to cancel the timeout timer if you hit Ctrl-C while running the collector in a terminal
	print("Received SIGINT, exiting.")
	os._exit(0)


signal.signal(signal.SIGINT, handle_sigint)

me = os.path.abspath(sys.argv[0])
my_stats = {
	"transactions.configured": 0,
	"data-points-collected": 0,
	"rest-api-requests": 0,
	"rest-api-responses": 0,
	"rest-api-failures": 0
}

print("{me}: Starting...".format(ts=datetime.datetime.utcnow(), me=me), file=sys.stderr)
timeout_timer = threading.Timer(SCRIPT_TIMEOUT, time_expired)
timeout_timer.start()

start_time = time.time();

try:
		requests.packages.urllib3.disable_warnings()
except AttributeError:
		pass

(config, config_file) = cccommon.initialize()
if not 'transactions' in config:
	print("{me}: No transactions in config. Exiting.".format(me=me), file=sys.stderr)
	os._exit(0)

print("{me}: Loaded configuration from {path}".format(me=me, path=os.path.abspath(config_file.name)), file=sys.stderr)

if not 'token' in config or not cccommon.check_token(config['token']):
	config['token'] = cccommon.authenticate(config, None)
	config_file.seek(0)
	config_file.truncate()
	json.dump(config, config_file, indent=4, sort_keys=True)
	print("{me}: Got token {token}".format(me=me, token=config['token']), file=sys.stderr)
else:
	print("{me}: Loaded valid token {token} from config".format(me=me, token=config['token']), file=sys.stderr)

if not 'app-info' in config:
	print("{me}: Getting app names...".format(me=me), file=sys.stderr)
	config['app-info'] = cccommon.get_app_info(config['token'])
	config_file.seek(0)
	config_file.truncate()
	json.dump(config, config_file, indent=4, sort_keys=True)

for txn in config['transactions']:
	if not 'token' in txn or not cccommon.check_tx_token(txn['token'], txn['appId']):
		txn['token'] = cccommon.authenticate(config, "app/" + txn['appId'] + "/transactions")
		config_file.seek(0)
		config_file.truncate()
		json.dump(config, config_file, indent=4, sort_keys=True)
		print("{me}: Got token {token}".format(me=me, token=txn['token']), file=sys.stderr)
	else:
		print("{me}: Loaded valid token {token} from config".format(me=me, token=txn['token']), file=sys.stderr)
	
	get_txn_data(txn['token'], txn['appId'])

timeout_timer.cancel()
end_time = time.time();

my_stats["time-taken"] = int(end_time - start_time)
ts = int(end_time)
tags = "collector=transactions.py"
for stat, value in my_stats.iteritems():
	print("{metric} {ts} {value} {tags}".format(metric="crittercism.collector." + stat, ts=ts, value=value, tags=tags))

print("{me}: Done, collected {points} data points in {t} seconds ({success}/{reqs} requests succeeded)".format(
	me=me, points=my_stats["data-points-collected"], t=int(end_time - start_time),
	success=my_stats["rest-api-responses"], reqs=my_stats["rest-api-requests"]),
	file=sys.stderr)
