#!/usr/bin/python
from __future__ import print_function

import os
import signal
import re
import sys
import base64
import requests
import json
import time
import datetime
import dateutil.parser
import threading

exepath = os.path.abspath(os.path.dirname(sys.argv[0]))
sys.path.append(exepath)
sys.path.append(exepath + '/..')
sys.path.append(exepath + '/../..')
sys.path.append(exepath + '/../etc')

import cccommon

SCRIPT_TIMEOUT = 900

def get_trends(appId, groupBy, sort, limit):
	
	params = {
				"params": {
					"appId": appId,
					"duration": 15,
					"sort": sort,
					"limit": limit,
					"groupBy": groupBy,
				}
			}
	metricprefix = "crittercism.trends."

	try:
		my_stats["rest-api-requests"] += 1
		response = requests.post(
			url="https://developers.crittercism.com/v1/apm/trends",
			headers={
				"Authorization": "Bearer " + config['token'],
				"Content-Type": "application/json",
			},
			data=json.dumps(params)
		)
		
		if response.status_code != 200:
			my_stats["rest-api-failures"] += 1
			print("Error loading trends: {code}".format(code=response.status_code), file=sys.stderr)
		else:
			my_stats["rest-api-responses"] += 1
			data = json.loads(response.content)
			start = dateutil.parser.parse(data['data']['start'])
			end = dateutil.parser.parse(data['data']['end'])
			interval = data['data']['interval']
			appId = data['params']['appId']
	
			mastertags = basic_tags_for_app(appId)
	
			point_names = map(cccommon.clean_for_opentsdb, data['data']['names'])
	
			for name, points in data['data']['series'].iteritems():
				metric = metricprefix + name + "." + groupBy
				print_trends(end, metric, mastertags, groupBy, points, point_names)

	except requests.exceptions.RequestException:
		my_stats["trends.failed"] += 1
		print('HTTP Request failed', file=sys.stderr)

def basic_tags_for_app(appId):
	tags = "appId={appId}".format(appId=appId)
	if 'app-info' in config and appId in config['app-info']:
		appName = cccommon.clean_for_opentsdb(config['app-info'][appId]['appName'])
		appType = cccommon.clean_for_opentsdb(config['app-info'][appId]['appType'])
		tags += " appName={appName} appType={appType}".format(appName=appName, appType=appType)
	return tags

def print_trends(dt, metric, common_tags, extra_tag_name, points, point_names):
	ts = int(time.mktime(dt.timetuple()))
	for point_name, point_value in zip(point_names, points):
		my_stats["data-points-collected"] += 1
		tags = "{common} {tag_name}={tag_value}".format(common=common_tags, tag_name=extra_tag_name, tag_value=point_name)
		print("{metric} {ts} {value} {tags}".format(metric=metric, ts=ts, value=point_value, tags=tags))

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
	"trends.configured": 0,
	"rest-api-requests": 0,
	"rest-api-responses": 0,
	"rest-api-failures": 0,
	"data-points-collected": 0
}

print("{me}: Starting...".format(me=sys.argv[0]), file=sys.stderr)
timeout_timer = threading.Timer(SCRIPT_TIMEOUT, time_expired)
timeout_timer.start()

start_time = time.time();

try:
		requests.packages.urllib3.disable_warnings()
except AttributeError:
		pass

(config, config_file) = cccommon.initialize()
print("{me}: Loaded configuration from {path}".format(me=me, path=os.path.abspath(config_file.name)), file=sys.stderr)

if not 'trends' in config:
	sys.exit("{me}: No trends found in config - nothing to do".format(me=me))

my_stats["trends.configured"] += len(config['trends'])

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

for trend in config['trends']:
	get_trends(trend['appId'], trend['groupBy'], trend['sort'], trend['limit'])

timeout_timer.cancel()
end_time = time.time();

my_stats["time-taken"] = int(end_time - start_time)
ts = int(end_time)
tags = "collector=trends.py"
for stat, value in my_stats.iteritems():
	print("{metric} {ts} {value} {tags}".format(metric="crittercism.collector." + stat, ts=ts, value=value, tags=tags))

print("{me}: Done, collected {points} data points in {t} seconds ({success}/{reqs} requests succeeded)".format(
	me=me, points=my_stats["data-points-collected"], t=int(end_time - start_time),
	success=my_stats["rest-api-responses"], reqs=my_stats["rest-api-requests"]),
	file=sys.stderr)
