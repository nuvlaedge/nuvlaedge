#!/usr/bin/env bash

OUTPUT_DIR=${1:-.}

mkdir -p $OUTPUT_DIR || true

poetry self add poetry-plugin-export

poetry export --format requirements.txt --output ${OUTPUT_DIR}/requirements.tests.txt --without-hashes --without-urls \
    --with tests \
    --with agent \
    --with kubernetes \
    --with system-manager \
    --with network \
    --with modbus \
    --with gpu \
    --with job-engine \
    --with bluetooth
