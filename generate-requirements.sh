#!/usr/bin/env bash

OUTPUT_DIR=${1:-.}

mkdir -p $OUTPUT_DIR || true

poetry export -f requirements.txt --output ${OUTPUT_DIR}/requirements.tests.txt --without-hashes --without-urls \
    --with tests \
    --with agent \
    --with system-manager \
    --with network \
    --with modbus \
    --with gpu \
    --with job-engine
