#!/usr/bin/env bash
# Run inside WSL2: bash scripts/start_mininet_server.sh
# Starts the Mininet topology server that the PathWise sandbox connects to.
set -e
echo "[PathWise] Starting Mininet topology server on WSL2 port 6000..."
cd "$(dirname "$0")/.."
sudo python ml/data_generation/mininet_topology_server.py
