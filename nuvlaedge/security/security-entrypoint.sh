#!/bin/sh

while [ true ]; do
    echo "Sleeping for 1 secs"
    sleep 1

    security $@
    exit_code=$?

    if [ $exit_code -ne 0 ]; then
        exit $exit_code
    fi
    echo "Sleeping for $SECURITY_SCAN_INTERVAL secs"
    sleep $SECURITY_SCAN_INTERVAL
done