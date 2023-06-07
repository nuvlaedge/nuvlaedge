# syntax=docker/dockerfile:1.4
ARG BASE_IMAGE=python:3.11.3-alpine3.18
ARG GO_BASE_IMAGE=golang:1.20.4-alpine3.18

# ------------------------------------------------------------------------
# Base builder stage containing the common python and alpine dependencies
# ------------------------------------------------------------------------
FROM ${BASE_IMAGE} AS base-builder
RUN apk update
RUN apk add gcc musl-dev linux-headers python3-dev libffi-dev

COPY --link requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt


# ------------------------------------------------------------------------
# Bluetooth Peripheral builder
# ------------------------------------------------------------------------
FROM base-builder AS bt-builder
RUN apk add git g++ bluez-dev

WORKDIR /tmp/
RUN git clone https://github.com/pybluez/pybluez.git

WORKDIR /tmp/pybluez

# Pybluez has no maintenance altough it accepts contributions. Lock it to the current commit sha
RUN git checkout 4d46ce1

RUN python setup.py install


# ------------------------------------------------------------------------
FROM base-builder AS network-builder

COPY --link requirements.network.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt


# ------------------------------------------------------------------------
FROM base-builder AS modbus-builder

COPY --link requirements.modbus.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt


# ------------------------------------------------------------------------
FROM base-builder AS gpu-builder

COPY --link requirements.gpu.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt


# ------------------------------------------------------------------------
# System Manager builder
# ------------------------------------------------------------------------
FROM base-builder AS system-manager-builder
RUN apk add openssl-dev openssl
RUN apk add py3-cryptography="40.0.2-r1"

RUN cp -r /usr/lib/python3.11/site-packages/cryptography/ /usr/local/lib/python3.11/site-packages/
RUN cp -r /usr/lib/python3.11/site-packages/cryptography-40.0.2.dist-info/ /usr/local/lib/python3.11/site-packages/

COPY --link requirements.system-manager.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt


# ------------------------------------------------------------------------
# Agent builder
# ------------------------------------------------------------------------
FROM base-builder AS agent-builder

COPY --link requirements.agent.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt


# ------------------------------------------------------------------------
# Job Engine builder
# ------------------------------------------------------------------------
FROM base-builder AS job-engine-builder

RUN apk add py3-bcrypt="4.0.1-r2" py3-pynacl
RUN cp -r /usr/lib/python3.11/site-packages/bcrypt/ /usr/local/lib/python3.11/site-packages/
RUN cp -r /usr/lib/python3.11/site-packages/bcrypt-4.0.1.dist-info/ /usr/local/lib/python3.11/site-packages/

RUN cp -r /usr/lib/python3.11/site-packages/nacl/ /usr/local/lib/python3.11/site-packages/
RUN cp -r /usr/lib/python3.11/site-packages/PyNaCl-1.5.0-py3.11.egg-info/ /usr/local/lib/python3.11/site-packages/


COPY --link requirements.job-engine.txt /tmp/requirements.lite.txt
RUN pip install -r /tmp/requirements.lite.txt


# ------------------------------------------------------------------------
FROM base-builder AS nuvlaedge-builder

# Extract and separate requirements from package install to accelerate building process.
# Package dependency install is the Slow part of the building process
COPY --link --from=agent-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --link --from=system-manager-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --link --from=job-engine-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --link --from=nuvla/job-lite:3.2.7 /usr/local/lib/python3.8/site-packages/nuvla /usr/local/lib/python3.11/site-packages/nuvla
COPY --link --from=network-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --link --from=modbus-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --link --from=bt-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --link --from=gpu-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

RUN pip install docker-compose

COPY --link dist/nuvlaedge-*.whl /tmp/
RUN pip install /tmp/nuvlaedge-*.whl

FROM ${GO_BASE_IMAGE} AS golang-builder
# Build Golang usb peripehral
RUN apk update
RUN apk add libusb-dev udev pkgconfig gcc musl-dev

COPY --link nuvlaedge/peripherals/usb/ /opt/usb/
WORKDIR /opt/usb/

RUN go mod tidy && go build


FROM ${BASE_IMAGE}
COPY --link --from=golang-builder /opt/usb/nuvlaedge /usr/sbin/usb

# ------------------------------------------------------------------------
# Required alpine packages
# ------------------------------------------------------------------------
COPY --link --from=nuvlaedge-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --link --from=nuvlaedge-builder /usr/local/bin /usr/local/bin


# ------------------------------------------------------------------------
# Library required by py-cryptography (pyopenssl).
# By copying it from base builder we save up ~100MB of the gcc library
# ------------------------------------------------------------------------
COPY --link --from=nuvlaedge-builder /usr/lib/libgcc_s.so.1 /usr/lib/


# ------------------------------------------------------------------------
# GPU Peripheral setup
# ------------------------------------------------------------------------
RUN mkdir /opt/scripts/
COPY --link nuvlaedge/peripherals/gpu/cuda_scan.py /opt/nuvlaedge/scripts/gpu/
COPY --link nuvlaedge/peripherals/gpu/Dockerfile.gpu /etc/nuvlaedge/scripts/gpu/


# ------------------------------------------------------------------------
# REquired packages for the Agent
# ------------------------------------------------------------------------
RUN apk update
RUN apk add --no-cache procps curl mosquitto-clients lsblk openssl


# ------------------------------------------------------------------------
# Required packages for USB peripheral discovery
# ------------------------------------------------------------------------
RUN apk add --no-cache libusb-dev udev


# ------------------------------------------------------------------------
# Required for bluetooth discovery
# ------------------------------------------------------------------------
RUN apk add --no-cache bluez-dev

# ------------------------------------------------------------------------
# Setup Compute-API
# ------------------------------------------------------------------------
RUN apk add --no-cache socat

COPY scripts/compute-api/api.sh /usr/bin/api
RUN chmod +x /usr/bin/api


# ------------------------------------------------------------------------
# Setup VPN Client
# ------------------------------------------------------------------------
RUN apk add --no-cache openvpn

COPY --link scripts/vpn-client/* /opt/nuvlaedge/scripts/vpn-client/
RUN mv /opt/nuvlaedge/scripts/vpn-client/openvpn-client.sh /usr/bin/openvpn-client
RUN chmod +x /usr/bin/openvpn-client
RUN chmod +x /opt/nuvlaedge/scripts/vpn-client/get_ip.sh
RUN chmod +x /opt/nuvlaedge/scripts/vpn-client/wait-for-vpn-update.sh


# ------------------------------------------------------------------------
# Copy configuration files
# ------------------------------------------------------------------------
COPY --link  nuvlaedge/agent/config/agent_logger_config.conf /etc/nuvlaedge/agent/config/agent_logger_config.conf


# ------------------------------------------------------------------------
# Set up Job engine
# ------------------------------------------------------------------------
RUN apk add --no-cache gettext docker-cli
RUN apk add --repository http://dl-cdn.alpinelinux.org/alpine/edge/community kubectl

COPY --link --from=nuvla/job-lite:3.2.7 /app/* /app/
WORKDIR /app
RUN wget -O my_init https://raw.githubusercontent.com/phusion/baseimage-docker/rel-0.9.19/image/bin/my_init && \
    chmod 700 /app/my_init
RUN ln -s /app/my_init /usr/bin/my_init
RUN ln -s $(which python3) /usr/bin/python3

VOLUME /etc/nuvlaedge/database

WORKDIR /opt/nuvlaedge/

ENTRYPOINT ["my_init"]