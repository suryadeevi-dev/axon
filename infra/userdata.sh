#!/bin/bash
# EC2 bootstrap script for AXON agent instances.
# Runs once at first launch via EC2 User Data.
# Ubuntu 22.04 LTS — SSM agent is pre-installed by Canonical.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y -qq \
  python3 python3-pip python3-venv \
  nodejs npm \
  git curl wget unzip jq \
  build-essential \
  ca-certificates

# Isolated agent user with a persistent workspace
id axon 2>/dev/null || useradd -m -s /bin/bash axon
mkdir -p /home/axon/workspace
chown -R axon:axon /home/axon

echo "AXON agent bootstrap complete at $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  >> /var/log/axon-init.log
