# syntax=docker/dockerfile:1.4

ARG ALPINE_MAJ_MIN_VERSION="3.18"
ARG PYTHON_MAJ_MIN_VERSION="3.11"
ARG GOLANG_VERSION="1.20.4"
ARG PYTHON_CRYPTOGRAPHY_VERSION="41.0.3"
ARG PYTHON_BCRYPT_VERSION="4.0.1"
ARG PYTHON_NACL_VERSION="1.5.0"
ARG JOB_LITE_VERSION="3.9.0"
ARG JOB_LITE_IMG_ORG="nuvla"

ARG PYTHON_SITE_PACKAGES="/usr/lib/python${PYTHON_MAJ_MIN_VERSION}/site-packages"
ARG PYTHON_LOCAL_SITE_PACKAGES="/usr/local/lib/python${PYTHON_MAJ_MIN_VERSION}/site-packages"

ARG BASE_IMAGE=python:${PYTHON_MAJ_MIN_VERSION}-alpine${ALPINE_MAJ_MIN_VERSION}
ARG GO_BASE_IMAGE=golang:${GOLANG_VERSION}-alpine${ALPINE_MAJ_MIN_VERSION}

# Import job-lite image
FROM ${JOB_LITE_IMG_ORG}/job-lite:${JOB_LITE_VERSION} AS job-lite


# ------------------------------------------------------------------------
# NuvlaEdge base image for labels and environments variables
# ------------------------------------------------------------------------
FROM ${BASE_IMAGE} AS nuvlaedge-base

ARG GIT_BRANCH
ARG GIT_COMMIT_ID
ARG GIT_BUILD_TIME
ARG GITHUB_RUN_NUMBER
ARG GITHUB_RUN_ID
ARG PROJECT_URL

ARG JOB_LITE_VERSION
ENV JOB_LITE_VERSION=${JOB_LITE_VERSION}

LABEL git.branch=${GIT_BRANCH} \
      git.commit.id=${GIT_COMMIT_ID} \
      git.build.time=${GIT_BUILD_TIME} \
      git.run.number=${GITHUB_RUN_NUMBER} \
      git.run.id=${GITHUB_RUN_ID}
LABEL org.opencontainers.image.authors="support@sixsq.com" \
      org.opencontainers.image.created=${GIT_BUILD_TIME} \
      org.opencontainers.image.url=${PROJECT_URL} \
      org.opencontainers.image.vendor="SixSq SA" \
      org.opencontainers.image.title="NuvlaEdge" \
      org.opencontainers.image.description="Common image for NuvlaEdge software components"


# ------------------------------------------------------------------------
# Base builder stage containing the common python and alpine dependencies
# ------------------------------------------------------------------------
FROM ${BASE_IMAGE} AS base-builder

RUN apk update
RUN apk add gcc musl-dev linux-headers python3-dev libffi-dev rust

COPY --link requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip
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

# this environment variable is set to fasten the install of dbus-fast.
# it will be fixed in the later versions of dbus-fast
ENV SKIP_CYTHON=false
COPY --link requirements.bluetooth.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt


# ------------------------------------------------------------------------
# Network Peripheral builder
# ------------------------------------------------------------------------
FROM base-builder AS network-builder

COPY --link requirements.network.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt


# ------------------------------------------------------------------------
# ModBus Peripheral builder
# ------------------------------------------------------------------------
FROM base-builder AS modbus-builder

COPY --link requirements.modbus.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt


# ------------------------------------------------------------------------
# GPU Peripheral builder
# ------------------------------------------------------------------------
FROM base-builder AS gpu-builder

COPY --link requirements.gpu.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt


# ------------------------------------------------------------------------
# USB Peripheral builder
# ------------------------------------------------------------------------
FROM ${GO_BASE_IMAGE} AS golang-builder

# Build Golang usb peripehral
RUN apk update
RUN apk add libusb-dev udev pkgconfig gcc musl-dev

COPY --link nuvlaedge/peripherals/usb/ /opt/usb/
WORKDIR /opt/usb/

RUN go mod tidy && go build


# ------------------------------------------------------------------------
# System Manager builder
# ------------------------------------------------------------------------
FROM base-builder AS system-manager-builder

ARG PYTHON_CRYPTOGRAPHY_VERSION
ARG PYTHON_SITE_PACKAGES
ARG PYTHON_LOCAL_SITE_PACKAGES

RUN apk add openssl-dev openssl
RUN apk add "py3-cryptography~${PYTHON_CRYPTOGRAPHY_VERSION}"

RUN cp -r ${PYTHON_SITE_PACKAGES}/cryptography/ ${PYTHON_LOCAL_SITE_PACKAGES}/
RUN cp -r ${PYTHON_SITE_PACKAGES}/cryptography-${PYTHON_CRYPTOGRAPHY_VERSION}.dist-info/ ${PYTHON_LOCAL_SITE_PACKAGES}/

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

ARG PYTHON_MAJ_MIN_VERSION
ARG PYTHON_BCRYPT_VERSION
ARG PYTHON_NACL_VERSION
ARG PYTHON_SITE_PACKAGES
ARG PYTHON_LOCAL_SITE_PACKAGES

RUN apk add "py3-bcrypt~${PYTHON_BCRYPT_VERSION}" "py3-pynacl~${PYTHON_NACL_VERSION}"

RUN cp -r ${PYTHON_SITE_PACKAGES}/bcrypt/ ${PYTHON_LOCAL_SITE_PACKAGES}/
RUN cp -r ${PYTHON_SITE_PACKAGES}/bcrypt-${PYTHON_BCRYPT_VERSION}.dist-info/ ${PYTHON_LOCAL_SITE_PACKAGES}/

RUN cp -r ${PYTHON_SITE_PACKAGES}/nacl/ ${PYTHON_LOCAL_SITE_PACKAGES}/
RUN cp -r ${PYTHON_SITE_PACKAGES}/PyNaCl-${PYTHON_NACL_VERSION}-py${PYTHON_MAJ_MIN_VERSION}.egg-info/ ${PYTHON_LOCAL_SITE_PACKAGES}/

COPY --link requirements.job-engine.txt /tmp/requirements.lite.txt
RUN pip install -r /tmp/requirements.lite.txt


# ------------------------------------------------------------------------
# NuvlaEdge builder
# ------------------------------------------------------------------------
FROM base-builder AS nuvlaedge-builder

ARG PYTHON_LOCAL_SITE_PACKAGES

# Extract and separate requirements from package install to accelerate building process.
# Package dependency install is the Slow part of the building process
COPY --link --from=agent-builder          ${PYTHON_LOCAL_SITE_PACKAGES}       ${PYTHON_LOCAL_SITE_PACKAGES}
COPY --link --from=system-manager-builder ${PYTHON_LOCAL_SITE_PACKAGES}       ${PYTHON_LOCAL_SITE_PACKAGES}
COPY --link --from=job-engine-builder     ${PYTHON_LOCAL_SITE_PACKAGES}       ${PYTHON_LOCAL_SITE_PACKAGES}
COPY --link --from=network-builder        ${PYTHON_LOCAL_SITE_PACKAGES}       ${PYTHON_LOCAL_SITE_PACKAGES}
COPY --link --from=modbus-builder         ${PYTHON_LOCAL_SITE_PACKAGES}       ${PYTHON_LOCAL_SITE_PACKAGES}
COPY --link --from=bt-builder             ${PYTHON_LOCAL_SITE_PACKAGES}       ${PYTHON_LOCAL_SITE_PACKAGES}
COPY --link --from=gpu-builder            ${PYTHON_LOCAL_SITE_PACKAGES}       ${PYTHON_LOCAL_SITE_PACKAGES}
COPY --link --from=job-lite               ${PYTHON_LOCAL_SITE_PACKAGES}/nuvla ${PYTHON_LOCAL_SITE_PACKAGES}/nuvla

COPY --link dist/nuvlaedge-*.whl /tmp/
RUN pip install /tmp/nuvlaedge-*.whl

# Cleanup python bytecode files
RUN find ${PYTHON_LOCAL_SITE_PACKAGES} -name '*.py?' -delete


# ------------------------------------------------------------------------
# Final NuvlaEdge image
# ------------------------------------------------------------------------
FROM nuvlaedge-base

ARG PYTHON_LOCAL_SITE_PACKAGES

# License
COPY LICENSE nuvlaedge/license.sh /opt/nuvlaedge/
RUN chmod +x /opt/nuvlaedge/license.sh
ONBUILD RUN ./license.sh

# Required packages
RUN apk add --no-cache \
        # Agent
        procps curl mosquitto-clients lsblk openssl iproute2 \
        # Modbus
        nmap nmap-scripts \
        # USB
        libusb-dev udev \ 
        # Bluetooth
        bluez-dev \
        # Security
        coreutils \
        # Compute-API
        socat \
        # OpenVPN
        openvpn \
		# Job-Engine
		gettext docker-cli docker-cli-compose helm
# Job-Engine and Kubernetes Credential Manager
RUN apk add --no-cache --repository http://dl-cdn.alpinelinux.org/alpine/edge/community kubectl

# Required python packages
COPY --link --from=nuvlaedge-builder ${PYTHON_LOCAL_SITE_PACKAGES} ${PYTHON_LOCAL_SITE_PACKAGES}
COPY --link --from=nuvlaedge-builder /usr/local/bin /usr/local/bin
# Library required by py-cryptography (pyopenssl).
# By copying it from base builder we save up ~100MB of the gcc library
COPY --link --from=nuvlaedge-builder /usr/lib/libgcc_s.so.1 /usr/lib/

# Peripheral discovery: USB
COPY --link --from=golang-builder /opt/usb/nuvlaedge /usr/sbin/usb

# Peripheral discovery: GPU
RUN mkdir /opt/scripts/
COPY --link nuvlaedge/peripherals/gpu/cuda_scan.py /opt/nuvlaedge/scripts/gpu/
COPY --link nuvlaedge/peripherals/gpu/Dockerfile.gpu /etc/nuvlaedge/scripts/gpu/

# Security module
# nmap nmap-scripts coreutils curl
COPY --link nuvlaedge/security/patch/vulscan.nse /usr/share/nmap/scripts/vulscan/
COPY --link nuvlaedge/security/security-entrypoint.sh /usr/bin/security-entrypoint
RUN chmod +x /usr/bin/security-entrypoint

# Compute API
COPY scripts/compute-api/api.sh /usr/bin/api
RUN chmod +x /usr/bin/api

# VPN Client
COPY --link scripts/vpn-client/* /opt/nuvlaedge/scripts/vpn-client/
RUN mv /opt/nuvlaedge/scripts/vpn-client/openvpn-client.sh /usr/bin/openvpn-client && \
    chmod +x /usr/bin/openvpn-client && \
    chmod +x /opt/nuvlaedge/scripts/vpn-client/get_ip.sh && \
    chmod +x /opt/nuvlaedge/scripts/vpn-client/wait-for-vpn-update.sh
# For backward compatibility with existing vpn/nuvlaedge.conf file
RUN ln -s /opt/nuvlaedge/scripts/vpn-client/get_ip.sh /opt/nuvlaedge/scripts/get_ip.sh && \
    ln -s /opt/nuvlaedge/scripts/vpn-client/wait-for-vpn-update.sh /opt/nuvlaedge/scripts/wait-for-vpn-update.sh

# Kubernetes credential manager
COPY --link scripts/credential-manager/* /opt/nuvlaedge/scripts/credential-manager/
RUN cp /opt/nuvlaedge/scripts/credential-manager/kubernetes-credential-manager.sh /usr/bin/kubernetes-credential-manager && \
    chmod +x /usr/bin/kubernetes-credential-manager

# Configuration files
COPY --link nuvlaedge/agent/config/agent_logger_config.conf /etc/nuvlaedge/agent/config/agent_logger_config.conf
COPY --link conf/example/* /etc/nuvlaedge/

# Job engine
COPY --link --from=job-lite /app/* /app/

# my_init
WORKDIR /app
RUN wget -O my_init https://raw.githubusercontent.com/phusion/baseimage-docker/rel-0.9.19/image/bin/my_init && \
    chmod 700 /app/my_init && \
    ln -s /app/my_init /usr/bin/my_init && \
    ln -s $(which python3) /usr/bin/python3


WORKDIR /opt/nuvlaedge/

ENTRYPOINT ["my_init"]
