#!/bin/bash

# This is a script to help set up the critter-bosun collector on top of the
# base stackexchange/bosun docker image.
#
# Create your ccconfig.json in the same directory with this file and the .py
# files before running this script.
#
# Set BOSUN_CONTAINER to the ID or name of the container you want to set up,
# otherwise the following will just look for the first container running the
# stackexchange/bosun image.
#
if [ -z "${BOSUN_CONTAINER}" ]; then
	BOSUN_CONTAINER=`docker ps --filter ancestor=stackexchange/bosun --format="{{.ID}}" | head -1`
fi

echo "Setting up critter-bosun on container ${BOSUN_CONTAINER}"
cat > /tmp/scollector.toml.$$ << EOF
ColDir = "/scollector/collectors"
BatchSize = 5000
EOF

cat > /tmp/ccsetup.$$ << EOF
apt-get update
apt-get install -y python-pip
apt-get install -y libevent-dev
apt-get install -y python-all-dev
pip install requests
pip install grequests
pip install python-dateutil
supervisorctl stop scollector && supervisorctl start scollector
EOF

#Setup Directories for default docker installation (for demo purposes)
docker exec ${BOSUN_CONTAINER} bash -c "mkdir -p /scollector/collectors/900"

#Copy Files
docker cp /tmp/scollector.toml.$$ ${BOSUN_CONTAINER}:/scollector/scollector.toml
docker cp /tmp/ccsetup.$$ ${BOSUN_CONTAINER}:/tmp/ccsetup

docker cp endpoints.py ${BOSUN_CONTAINER}:/scollector/collectors/900/endpoints.py
docker cp trends.py ${BOSUN_CONTAINER}:/scollector/collectors/900/trends.py
docker cp transactions.py ${BOSUN_CONTAINER}:/scollector/collectors/900/transactions.py
docker cp cccommon.py ${BOSUN_CONTAINER}:/scollector/cccommon.py
docker cp ccconfig.json ${BOSUN_CONTAINER}:/scollector/ccconfig.json

docker cp bosun-example.conf ${BOSUN_CONTAINER}:/data/bosun.conf

# Run the setup script in the container
docker exec ${BOSUN_CONTAINER} bash -c "source /tmp/ccsetup"
echo "Done for ${BOSUN_CONTAINER}"
