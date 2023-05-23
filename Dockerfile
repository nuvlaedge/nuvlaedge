ARG BASE_IMAGE=python:3.11.3-alpine3.18
ARG GO_BASE_IMAGE=golang:1.20.4-alpine3.18

# Base builder stage containing the common python and alpine dependencies
FROM ${BASE_IMAGE} AS base-builder
RUN apk update
RUN apk add gcc musl-dev linux-headers python3-dev

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

FROM base-builder AS agent-builder

COPY requirements.agent.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

FROM base-builder AS system-manager-builder
RUN apk add openssl-dev openssl libffi-dev

COPY requirements.system-manager.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

FROM base-builder AS network-builder

COPY requirements.network.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

FROM base-builder AS modbus-builder

COPY requirements.modbus.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

FROM base-builder AS nuvlaedge-builder

# Extract and separate requirements from package install to accelerate building process.
# Package dependency install is the Slow part of the building process
COPY --from=agent-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=system-manager-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=network-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=modbus-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

COPY dist/nuvlaedge-*.whl /tmp/
RUN pip install /tmp/nuvlaedge-*.whl


FROM ${GO_BASE_IMAGE} AS golang-builder
# Build Golang usb peripehral
RUN apk update
RUN apk add libusb-dev udev pkgconfig gcc musl-dev

COPY nuvlaedge/peripherals/usb/ /opt/usb/
WORKDIR /opt/usb/

RUN go mod tidy && go build


FROM ${BASE_IMAGE}
COPY --from=golang-builder /opt/usb/nuvlaedge /usr/sbin/usb

# Required alpine packages
COPY --from=nuvlaedge-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=nuvlaedge-builder /usr/local/bin /usr/local/bin

# REquired packages for the Agent
RUN apk update
RUN apk add --no-cache procps curl mosquitto-clients openssl lsblk

# Required packages for USB peripheral discovery
RUN apk add --no-cache libusb-dev udev

# Copy configuration files
COPY nuvlaedge/agent/config/agent_logger_config.conf /etc/nuvlaedge/agent/config/agent_logger_config.conf

VOLUME /etc/nuvlaedge/database

WORKDIR /opt/
