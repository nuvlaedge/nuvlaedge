ARG BASE_IMAGE=python:3.11.3-alpine3.18
ARG GO_BASE_IMAGE=golang:1.20.4-alpine3.18
FROM ${BASE_IMAGE} AS nuvlaedge-builder

RUN apk update
RUN apk add curl libffi-dev gcc musl-dev py3-bluez

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

# Required to install pybluez
COPY --from=nuvlaedge-builder /usr/lib/python3.11/site-packages/bluetooth /usr/local/lib/python3.11/site-packages/bluetooth
COPY --from=nuvlaedge-builder /usr/lib/libbluetooth.so.3.19.8 /usr/lib/libbluetooth.so.3

# REquired packages for the Agent
RUN apk update
RUN apk add --no-cache procps curl mosquitto-clients openssl lsblk

# Required packages for USB peripheral discovery
RUN apk add --no-cache libusb-dev udev

# Copy configuration files
COPY nuvlaedge/agent/config/agent_logger_config.conf /etc/nuvlaedge/agent/config/agent_logger_config.conf

VOLUME /etc/nuvlaedge/database

WORKDIR /opt/
