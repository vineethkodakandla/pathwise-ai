#!/bin/bash
# Start the SD-WAN reference topology with remote SDN controller

set -e

CONTROLLER_IP=${CONTROLLER_IP:-"127.0.0.1"}
CONTROLLER_PORT=${CONTROLLER_PORT:-6633}

echo "Starting OVS service..."
service openvswitch-switch start

echo "Launching SD-WAN topology (controller: ${CONTROLLER_IP}:${CONTROLLER_PORT})..."
mn --custom /topologies/sdwan_topology.py \
   --topo sdwan \
   --controller=remote,ip=${CONTROLLER_IP},port=${CONTROLLER_PORT} \
   --switch ovsk,protocols=OpenFlow13 \
   --link tc
