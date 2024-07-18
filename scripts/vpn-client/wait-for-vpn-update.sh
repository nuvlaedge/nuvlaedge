#!/bin/sh

source /opt/nuvlaedge/scripts/vpn-client/.env

timestamp_nb_conf=$(stat -c %Y ${VPN_CONF})

# keep watching for updates on the NB VPN configuration file
timestamp_nb_updated=$timestamp_nb_conf
while [[ "$timestamp_nb_updated" -le "$timestamp_nb_conf" ]]
do
    timestamp_nb_updated=$(stat -c %Y ${VPN_CONF})
    sleep 1
done

# if we got here, then the nb.conf was updated and we must restart the openvpn-client
killall openvpn