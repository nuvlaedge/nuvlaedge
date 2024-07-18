#!/bin/sh


header_message="NuvlaEdge OpenVPN Client
\n\n
This microservice is responsible for setting up the VPN client
for the NuvlaEdge.
\n\n
Arguments:\n
  No arguments are expected.\n
  This message will be shown whenever -h, --help or help is provided and a
  command to the Docker container.\n
"


SOME_ARG="$1"

help_info() {
    echo "COMMAND: ${1}. You have asked for help:"
    echo -e ${header_message}
    exit 0
}


if [[ ! -z ${SOME_ARG} ]]
then
    if [[ "${SOME_ARG}" = "-h" ]] || [[ "${SOME_ARG}" = "--help" ]] || [[ "${SOME_ARG}" = "help" ]]
    then
        help_info ${SOME_ARG}
    else
        echo "WARNING: this container does not expect any arguments, thus they'll be ignored"
    fi
fi

##############

source /opt/nuvlaedge/scripts/vpn-client/.env

timeout 120 sh -c -- "echo 'INFO: waiting for '${VPN_CONF}
until [[ -f ${VPN_CONF} ]]
do
    sleep 3
    continue
done
"

if [[ $? -eq 0 ]]
then
  # Start the openvpn client in foreground
  echo "INFO: starting VPN client with configuration file ${VPN_CONF}"
  exec openvpn ${VPN_CONF}
fi