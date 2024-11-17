#!/usr/bin/env bash

IMAGE_ORG=${1:-local}
IMAGE_REPO=${2:-nuvlaedge}

export nuvlaedge_version=$(poetry version -s)
export IMAGE_TAG_NAME=$IMAGE_ORG/$IMAGE_REPO:${3:-$nuvlaedge_version}

rm -rf dist/*

poetry build --no-interaction --format=wheel
poetry export --format requirements.txt --output requirements.txt --without-hashes --without-urls
poetry export --format requirements.txt --output requirements.agent.txt --without-hashes --without-urls --with agent
poetry export --format requirements.txt --output requirements.kubernetes.txt --without-hashes --without-urls --with kubernetes
poetry export --format requirements.txt --output requirements.system-manager.txt --without-hashes --without-urls --with system-manager
poetry export --format requirements.txt --output requirements.network.txt --without-hashes --without-urls --with network
poetry export --format requirements.txt --output requirements.modbus.txt --without-hashes --without-urls --with modbus
poetry export --format requirements.txt --output requirements.gpu.txt --without-hashes --without-urls --with gpu
poetry export --format requirements.txt --output requirements.job-engine.txt --without-hashes --without-urls --with job-engine
poetry export --format requirements.txt --output requirements.bluetooth.txt --without-hashes --without-urls --with bluetooth

docker build --build-arg PACKAGE_TAG=$nuvlaedge_version -t ${IMAGE_TAG_NAME} .
echo $IMAGE_TAG_NAME