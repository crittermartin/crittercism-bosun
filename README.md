critter-bosun
=============


These are experimental collectors for use with bosun's scollector, though they
should also work with OpenTSDB's tcollector.

Configuration is in **ccconfig.json**. See ccconfig-example.json for an overview
of the configuration file structure.

**configure.py** is a config file generator; you can supply your REST Client ID,
username and password and it will generate a basic configuration for you.

**bosun-docker-setup.sh** can set up the critter-bosun collector inside a
Docker container running the stackexchange/bosun image -- set the environment
variable BOSUN_CONTAINER to the ID or name of the container you want to configure;
if you don't set the variable, the script will configure the first container
that is running the stackexchange/bosun image as output by 'docker ps'. This
script installs a lot of packages, so it can take a long time; please be patient!

In theory, you should be able to get a working instance of all this by doing the following:

    docker run -d -p 4242:4242 -p 8070:8070 stackexchange/bosun
    ./configure.py
    ./bosun-docker-setup.sh

**Collector scripts:**

-   **endpoints.py** - collects information on endpoints listed in the
    'endpoints' array in ccconfig.json, and on services listed in the
    'services' array; in addition 'endpoints-auto' and 'services-auto'
    can be used in ccconfig.json instead to collect information on the 
    top <limit> endpoints/services; or you can use a combination of manual
    and automatic endpoints and services by specifying both 'endpoints'
    and 'endpoints-auto'.

-   **trends.py** - collects performance trend information as specified in the
    'trends' array in ccconfig.json

-   **transactions.py** - collects transaction data as specified in the
    'transactions' array in ccconfig.json

These scripts generate and cache OAuth2 tokens; this means that REST Client ID,
Username and Password are optional; if present they will be used to obtain and
refresh the OAuth2 token when it expires; OAuth2 tokens obtained by the script
are stored back into ccconfig.json (this means that the formatting and order of 
this file can be changed when the scripts run)

**Example directory layout:**

    scollector/
    scollector/scollector.toml
    scollector/collectors/
    scollector/collectors/900/
    scollector/collectors/900/endpoints.py
    scollector/collectors/900/trends.py
    scollector/collectors/900/transactions.py
    scollector/ccconfig.json
    scollector/cccommon.py


**Collected Metrics:**

Collectors populate data into the following keys in OpenTSDB:

**endpoints.py:**

    crittercism.endpoint.data_in
    crittercism.endpoint.data_out
    crittercism.endpoint.errors
    crittercism.endpoint.errors.type
    crittercism.endpoint.latency
    crittercism.endpoint.latency.carrier
    crittercism.endpoint.latency.device
    crittercism.endpoint.volume
    crittercism.endpoint.volume.carrier
    crittercism.endpoint.volume.device
    crittercism.service.data_in
    crittercism.service.data_out
    crittercism.service.errors
    crittercism.service.errors.type
    crittercism.service.latency
    crittercism.service.latency.carrier
    crittercism.service.latency.device
    crittercism.service.volume
    crittercism.service.volume.carrier
    crittercism.service.volume.device

**transactions.py:**

    crittercism.transactions.crashed
    crittercism.transactions.longRunning
    crittercism.transactions.revenueAtRisk
    crittercism.transactions.succeeded
    crittercism.transactions.timedOut
    crittercism.transactions.userFailed
    crittercism.transactions.volume

**trends.py:**

    crittercism.trends.crashes.appVersion
    crittercism.trends.crashes.device
    crittercism.trends.crashes.os
    crittercism.trends.errors.appVersion
    crittercism.trends.errors.device
    crittercism.trends.errors.os
    crittercism.trends.latency.appVersion
    crittercism.trends.latency.device
    crittercism.trends.latency.os
    crittercism.trends.userbase.appVersion
    crittercism.trends.userbase.device
    crittercism.trends.userbase.os
    crittercism.trends.volume.appVersion
    crittercism.trends.volume.device
    crittercism.trends.volume.os

Metrics are tagged with app ID and other relevant info (for example, crittercism.trends.errors.appVersion is tagged with appVersion) - Bosun is a great tool for inspecting these tags and their values.

Each collector also collects information about how it is configured and how long it takes to run, as well as statistics about REST API requests and failures, in the following keys:

    crittercism.collector.data-points-collected
    crittercism.collector.endpoints.configured
    crittercism.collector.rest-api-failures
    crittercism.collector.rest-api-requests
    crittercism.collector.rest-api-responses
    crittercism.collector.services.configured
    crittercism.collector.time-taken
    crittercism.collector.transactions.configured
    crittercism.collector.trends.configured


**Note:**

OpenTSDB can't handle non-ASCII characters or spaces in metric names and tags; where spaces and Unicode characters occur in the data, they are usually replaced by "-".

**Resources:**

Bosun: <http://bosun.org>

SCollector doc: <http://bosun.org/scollector/external-collectors>

OpenTSDB: <http://opentsdb.net>
