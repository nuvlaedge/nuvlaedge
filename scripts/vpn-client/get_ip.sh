#!/bin/sh

source /opt/nuvlaedge/scripts/vpn-client/.env
# the openvpn client automatically passes the VPN IP into this script
echo $4 > ${VPN_IP}

BASEDIR=$(dirname "$0")

${BASEDIR}/wait-for-vpn-update.sh &