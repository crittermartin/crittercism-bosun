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

exepath = os.path.abspath(os.path.dirname(sys.argv[0]))
sys.path.append(exepath)
sys.path.append(exepath + '/..')
sys.path.append(exepath + '/../..')
sys.path.append(exepath + '/../etc')

import cccommon

SCRIPT_TIMEOUT = 900
MAX_CONCURRENT_API_CALLS = 50
LATENCY_DETAILS_TRACKED_DEVICES = 25
LATENCY_DETAILS_TRACKED_CARRIERS = 25

def get_basic_stats(endpoints):
	graphs = ["volume", "latency", "errors", "data"]
	rs = []
	
	for endpoint in endpoints:
		params = {
					"params": {
						"appId": endpoint['appId'],
						"filters": {
							"filterName": "0",
							"filterValue": "0"
						},
						"graph": "latency",
						"duration": 60
					}
				}
	
		if 'domain' in endpoint:
			params['params']['filters']['domain'] = endpoint['domain']
		if 'service' in endpoint:
			params['params']['filters']['service'] = endpoint['service']
		if 'endpoint' in endpoint:
			params['params']['filters']['endpoint'] = endpoint['endpoint']
		
		for graph in graphs:
			params["params"]["graph"] = graph
			r = grequests.post(
				url="https://developers.crittercism.com/v1/apm/graph",
				headers={
					"Authorization": "Bearer " + config['token'],
					"Content-Type": "application/json",
				},
				data=json.dumps(params)
			)
			rs.append(r)

	my_stats["rest-api-requests"] += len(rs)
	print("{me}: Sending {count} graph requests to Crittercism".format(me=me, count=len(rs)), file=sys.stderr)
	responses = grequests.map(rs, size=MAX_CONCURRENT_API_CALLS)

	for response in responses:
		(ok, data) = cccommon.check_apm_api_response(response)
		if not ok:
			my_stats["rest-api-failures"] += 1
			url = response.request.url
			print("{me}: {error} for {url}".format(me=me, error=data, url=url), file=sys.stderr)
			continue
		
		my_stats["rest-api-responses"] += 1
		start = dateutil.parser.parse(data['data']['start'])
		end = dateutil.parser.parse(data['data']['end'])
		interval = data['data']['interval']
		appId = data['params']['appId']

		mastertags = basic_tags_for_app(appId)
		metricprefix = "crittercism.service."

		filters = data['params']['filters']
		if 'domain' in filters:
			mastertags += " domain={domain}".format(domain=cccommon.clean_for_opentsdb(filters['domain']))
		if 'service' in filters:
			mastertags += " service={service}".format(service=filters['service'])
		if 'endpoint' in filters:
			metricprefix = "crittercism.endpoint."
			mastertags += " endpoint={endpoint}".format(endpoint=cccommon.clean_for_opentsdb(filters['endpoint']))

		for series in data["data"]["series"]:
			print_points(start, interval, metricprefix + series["name"], mastertags, series["points"])

def get_latency_detail(endpoints):

	rs = []
	
	for endpoint in endpoints:

		params = {
					"params": {
						"appId": endpoint['appId'],
						"filters": {
							"filterName": "0",
							"filterValue": "0"
						},
						"graph": "latency",
						"duration": 60
					}
				}
	
		if 'domain' in endpoint:
			params['params']['filters']['domain'] = endpoint['domain']
		if 'service' in endpoint:
			params['params']['filters']['service'] = endpoint['service']
		if 'endpoint' in endpoint:
			params['params']['filters']['endpoint'] = endpoint['endpoint']

		r = grequests.post(
			url="https://developers.crittercism.com/v1/apm/graphdetail",
			headers={
				"Authorization": "Bearer " + config['token'],
				"Content-Type": "application/json",
			},
			data=json.dumps(params)
		)
		rs.append(r)

	if len(rs) == 0:
		# nothing to do
		return

	my_stats["rest-api-requests"] += len(rs)
	print("{me}: Sending {count} latency detail requests to Crittercism".format(me=me, count=len(rs)), file=sys.stderr)
	responses = grequests.map(rs, size=MAX_CONCURRENT_API_CALLS)

	for response in responses:
		(ok, data) = cccommon.check_apm_api_response(response)
		if not ok:
			my_stats["rest-api-failures"] += 1
			url = response.request.url
			print("{me}: {error} for {url}".format(me=me, error=data, url=url), file=sys.stderr)
			continue
		
		my_stats["rest-api-responses"] += 1
		
		start = dateutil.parser.parse(data['data']['start'])
		end = dateutil.parser.parse(data['data']['end'])
		interval = data['data']['interval']
		
		masterseriespoints = data['data']['series'][0]['points'];
		deviceseries = data['data']['series'][1]['subseries'];
		carrierseries = data['data']['series'][2]['subseries'];
		appId = data['params']['appId']

		mastertags = basic_tags_for_app(appId)
		metricprefix = "crittercism.service."

		filters = data['params']['filters']
		if 'domain' in filters:
			mastertags += " domain={domain}".format(domain=cccommon.clean_for_opentsdb(filters['domain']))
		if 'service' in filters:
			mastertags += " service={service}".format(service=filters['service'])
		if 'endpoint' in filters:
			metricprefix = "crittercism.endpoint."
			mastertags += " endpoint={endpoint}".format(endpoint=cccommon.clean_for_opentsdb(filters['endpoint']))

		deviceseries.sort(key=lambda series: sum(series['volume']), reverse=True)
		carrierseries.sort(key=lambda series: sum(series['volume']), reverse=True)

		for series in deviceseries[:LATENCY_DETAILS_TRACKED_DEVICES]:
			clean_device_name = cccommon.clean_for_opentsdb(series['name'])
			if not clean_device_name or clean_device_name == "":
				clean_device_name = cccommon.clean_for_opentsdb(series['label'])

			num_latency_points = sum([1 for x in series['volume'] if x > 0])
			avg_latency = sum(series['points']) / num_latency_points
			total_volume = sum(series['volume'])

			print_point(metricprefix + "latency.device", int(time.mktime(start.timetuple())), avg_latency, mastertags + " device={device}".format(device=clean_device_name))
			print_point(metricprefix + "volume.device", int(time.mktime(start.timetuple())), total_volume, mastertags + " device={device}".format(device=clean_device_name))
		
		for series in carrierseries[:LATENCY_DETAILS_TRACKED_CARRIERS]:
			clean_carrier_name = cccommon.clean_for_opentsdb(series['name'])
			if clean_carrier_name == "":
				clean_carrier_name = "Unknown"

			num_latency_points = sum([1 for x in series['volume'] if x > 0])
			avg_latency = sum(series['points']) / num_latency_points
			total_volume = sum(series['volume'])

			print_point(metricprefix + "latency.carrier", int(time.mktime(start.timetuple())), avg_latency, mastertags + " carrier={carrier}".format(carrier=clean_carrier_name))
			print_point(metricprefix + "volume.carrier", int(time.mktime(start.timetuple())), total_volume, mastertags + " carrier={carrier}".format(carrier=clean_carrier_name))

def get_error_detail(endpoints):
	rs = []
	
	for endpoint in endpoints:
		params = {
					"params": {
						"appId": endpoint['appId'],
						"filters": {
							"filterName": "0",
							"filterValue": "0",
						},
						"duration": 60
					}
				}
	
		if 'domain' in endpoint:
			params['params']['filters']['domain'] = endpoint['domain']
		if 'service' in endpoint:
			params['params']['filters']['service'] = endpoint['service']
		if 'endpoint' in endpoint:
			params['params']['filters']['endpoint'] = endpoint['endpoint']
	
		r = grequests.post(
			url="https://developers.crittercism.com/v1/apm/errordetail",
			headers={
				"Authorization": "Bearer " + config['token'],
				"Content-Type": "application/json",
			},
			data=json.dumps(params)
		)
		rs.append(r)
	
	my_stats["rest-api-requests"] += len(rs)
	print("{me}: Sending {count} error detail requests to Crittercism".format(me=me, count=len(rs)), file=sys.stderr)
	responses = grequests.map(rs, size=MAX_CONCURRENT_API_CALLS)

	for response in responses:
		(ok, data) = cccommon.check_apm_api_response(response)
		if not ok:
			my_stats["rest-api-failures"] += 1
			url = response.request.url
			print("{me}: {error} for {url}".format(me=me, error=data, url=url), file=sys.stderr)
			continue
		
		my_stats["rest-api-responses"] += 1

		start = dateutil.parser.parse(data['data']['start'])
		end = dateutil.parser.parse(data['data']['end'])
		interval = data['data']['interval']
		appId = data['params']['appId']

		mastertags = basic_tags_for_app(appId)
		
		metricprefix = "crittercism.service."
		filters = data['params']['filters']
		if 'domain' in filters:
			mastertags += " domain={domain}".format(domain=cccommon.clean_for_opentsdb(filters['domain']))
		if 'service' in filters:
			mastertags += " service={service}".format(service=filters['service'])
		if 'endpoint' in filters:
			metricprefix = "crittercism.endpoint."
			mastertags += " endpoint={endpoint}".format(endpoint=cccommon.clean_for_opentsdb(filters['endpoint']))

		metric = metricprefix + "errors.type"

		serieslookup = {}
		for prefix, table in data['data']['errorTables'].iteritems():
			for code, value in table['mapping'].iteritems():
				key = prefix + ":" + code
				mapping = cccommon.clean_for_opentsdb(value)
				if key.startswith('h:'):
					mapping = "{code}-{mapping}".format(code=code, mapping=mapping)
				serieslookup[key] = mapping

		for series in data['data']['series']:
			print_points(start, interval, metric, mastertags + " type={type}".format(type=serieslookup[series['name']]), series['points'])		

def get_auto_endpoints(app):
	
	limit = 100
	if 'limit' in app:
		limit = app['limit']
	
	latency_detail = False
	if 'latency-detail' in app and app['latency-detail']:
		latency_detail = True

	my_stats["endpoints.configured"] += limit

	params = {
				"params": {
					"limit": limit,
					"appId": app['appId'],
					"sort": "volume",
					"duration": 60
				}
			}
	try:
		response = requests.post(
			url="https://app.crittercism.com/v1/apm/endpoints",
			headers={
				"Authorization": "Bearer " + config['token'],
				"Content-Type": "application/json",
			},
			data=json.dumps(params)
		)
		data = json.loads(response.content)

		endpoints = [ {'appId': app['appId'], 'domain': endpoint['d'], 'endpoint': endpoint['u'], 'service': endpoint['svc'], 'latency-detail': latency_detail} for endpoint in data['data']['endpoints'] ]

		return endpoints

	except requests.exceptions.RequestException:
		print('HTTP Request failed')

def get_auto_services(app):
	
	limit = 100
	if 'limit' in app:
		limit = app['limit']

	latency_detail = False
	if 'latency-detail' in app and app['latency-detail']:
		latency_detail = True

	my_stats["services.configured"] += limit

	params = {
				"params": {
					"limit": limit,
					"appId": app['appId'],
					"sort": "volume",
					"duration": 60
				}
			}
	try:
		response = requests.post(
			url="https://app.crittercism.com/v1/apm/services",
			headers={
				"Authorization": "Bearer " + config['token'],
				"Content-Type": "application/json",
			},
			data=json.dumps(params)
		)
		data = json.loads(response.content)

		services = [ {'appId': app['appId'], 'service': service['name'], 'latency-detail': latency_detail} for service in data['data']['services'] ]

		return services

	except requests.exceptions.RequestException:
		print('HTTP Request failed')

def basic_tags_for_app(appId):
	tags = "appId={appId}".format(appId=appId)
	if 'app-info' in config and appId in config['app-info']:
		appName = cccommon.clean_for_opentsdb(config['app-info'][appId]['appName'])
		appType = cccommon.clean_for_opentsdb(config['app-info'][appId]['appType'])
		tags += " appName={appName} appType={appType}".format(appName=appName, appType=appType)
	return tags

def print_points(start, interval, metric, tags, points):
	for i, point in enumerate(points):
		pointdt = start + datetime.timedelta(seconds=interval*i)
		ts = int(time.mktime(pointdt.timetuple()))
		print_point(metric, ts, point, tags)

def print_point(metric, ts, value, tags):
	my_stats["data-points-collected"] += 1
	print("{metric} {ts} {value} {tags}".format(metric=metric, ts=ts, value=value, tags=tags))

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
	"endpoints.configured": 0,
	"services.configured": 0,
	"rest-api-requests": 0,
	"rest-api-responses": 0,
	"rest-api-failures": 0,
	"data-points-collected": 0
}

print("{me}: Starting...".format(me=me), file=sys.stderr)
timeout_timer = threading.Timer(SCRIPT_TIMEOUT, time_expired)
timeout_timer.start()

start_time = time.time();

try:
		requests.packages.urllib3.disable_warnings()
except AttributeError:
		pass

(config, config_file) = cccommon.initialize()
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

stuff_to_monitor = []

if 'endpoints' in config:
	my_stats["endpoints.configured"] += len(config['endpoints'])
	stuff_to_monitor.extend(config['endpoints'])

if 'services' in config:
	my_stats["services.configured"] += len(config['services'])
	stuff_to_monitor.extend(config['services'])

if 'endpoints-auto' in config:
	for app in config['endpoints-auto']:
		stuff_to_monitor.extend(get_auto_endpoints(app))

if 'services-auto' in config:
	for app in config['services-auto']:
		stuff_to_monitor.extend(get_auto_services(app))

get_basic_stats(stuff_to_monitor)
get_error_detail(stuff_to_monitor)
get_latency_detail(stuff_to_monitor)

timeout_timer.cancel()
end_time = time.time();

my_stats["time-taken"] = int(end_time - start_time)
ts = int(end_time)
tags = "collector=endpoints.py"
for stat, value in my_stats.iteritems():
	print("{metric} {ts} {value} {tags}".format(metric="crittercism.collector." + stat, ts=ts, value=value, tags=tags))

print("{me}: Done, collected {points} data points in {t} seconds ({success}/{reqs} requests succeeded)".format(
	me=me, points=my_stats["data-points-collected"], t=int(end_time - start_time),
	success=my_stats["rest-api-responses"], reqs=my_stats["rest-api-requests"]),
	file=sys.stderr)
