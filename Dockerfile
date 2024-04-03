# syntax=docker/dockerfile:1.4

ARG ALPINE_MAJ_MIN_VERSION="3.18"
ARG PYTHON_MAJ_MIN_VERSION="3.11"
ARG GOLANG_VERSION="1.20.4"
ARG PYTHON_CRYPTOGRAPHY_VERSION="41.0.3"
ARG PYTHON_BCRYPT_VERSION="4.0.1"
ARG PYTHON_NACL_VERSION="1.5.0"
ARG JOB_LITE_VERSION="3.9.3"
ARG JOB_LITE_IMG_ORG="nuvla"
ARG PYDANTIC_VERSION="2.6.4-r0"
ARG PYDANTIC_CORE_VERSION="2.16.3-r0"

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

ARG PYDANTIC_VERSION
ARG PYDANTIC_CORE_VERSION
ARG PYTHON_SITE_PACKAGES
ARG PYTHON_LOCAL_SITE_PACKAGES

RUN apk update
RUN apk add gcc musl-dev linux-headers python3-dev libffi-dev upx curl

# Install pydantic form source to prevent bulding locally
RUN apk add "py3-pydantic~${PYDANTIC_VERSION}" "py3-pydantic-core~${PYDANTIC_CORE_VERSION}" --repository=https://dl-cdn.alpinelinux.org/alpine/edge/community
RUN cp -r ${PYTHON_SITE_PACKAGES}/* ${PYTHON_LOCAL_SITE_PACKAGES}/

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

WORKDIR /tmp
RUN apk update; apk add nmap-scripts

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
RUN apk add libusb-dev udev pkgconfig gcc musl-dev upx

COPY --link nuvlaedge/peripherals/usb/ /opt/usb/
WORKDIR /opt/usb/

RUN go mod tidy && \
    go build && \
    upx --lzma /opt/usb/nuvlaedge


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
FROM docker AS docker
FROM base-builder AS agent-builder

ARG PYTHON_LOCAL_SITE_PACKAGES

# Docker and docker compose CLIs
COPY --from=docker /usr/local/bin/docker /usr/bin/docker
COPY --from=docker /usr/local/libexec/docker/cli-plugins/docker-compose \
                   /usr/local/libexec/docker/cli-plugins/docker-compose

# Kubectl CLI
RUN set -eux; \
    apkArch="$(apk --print-arch)"; \
    case "$apkArch" in \
        x86_64)  kubectlArch='amd64' ;; \
        armv7)   kubectlArch='arm' ;; \
        aarch64) kubectlArch='arm64' ;; \
        *) echo >&2 "error: unsupported architecture ($apkArch) for kubectl"; exit 1 ;;\
    esac; \
    kubectlVersion=$(curl -Ls https://dl.k8s.io/release/stable.txt); \
    curl -LO https://dl.k8s.io/release/${kubectlVersion}/bin/linux/${kubectlArch}/kubectl && \
    chmod +x ./kubectl && \
    mv ./kubectl /usr/local/bin/kubectl

# Helm CLI
RUN curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | VERIFY_CHECKSUM=false sh

# Compress binaires
RUN upx --lzma \
        /usr/bin/docker \
        /usr/local/libexec/docker/cli-plugins/docker-compose \
        /usr/local/bin/kubectl \
        /usr/local/bin/helm

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

ARG PYTHON_MAJ_MIN_VERSION
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

# Remove setuptools and pip
RUN pip uninstall -y setuptools
RUN pip uninstall -y pip

# Remove psutil tests
RUN rm -rf ${PYTHON_LOCAL_SITE_PACKAGES}/psutil/tests

# Cleanup python bytecode files
RUN find ${PYTHON_LOCAL_SITE_PACKAGES} -name '*.py?' -delete
RUN find /usr/local/lib/python${PYTHON_MAJ_MIN_VERSION} -name '*.py?' -delete


# ------------------------------------------------------------------------
# Final NuvlaEdge image
# ------------------------------------------------------------------------
FROM nuvlaedge-base

ARG PYTHON_MAJ_MIN_VERSION

#RUN rm -f /lib/libcrypto.so.3 && \
#RUN rm -Rf /usr/lib/python${PYTHON_MAJ_MIN_VERSION}/ensurepip && \
#    pip uninstall -y setuptools && \
#    pip uninstall -y pip

ARG PYTHON_LOCAL_SITE_PACKAGES

# License
COPY LICENSE nuvlaedge/license.sh /opt/nuvlaedge/
RUN chmod +x /opt/nuvlaedge/license.sh
ONBUILD RUN ./license.sh

# Required packages
RUN apk add --no-cache upx \
        # Agent
        procps curl mosquitto-clients lsblk openssl iproute2-minimal \
        # Modbus and Security
        nmap nmap-nselibs \
        # USB
        libusb-dev udev \
        # Bluetooth
        bluez-dev \
        # Security
        coreutils \
        # Compute API
        socat \
        # VPN client
        openvpn \
		# Job-Engine (envsubst for k8s substitution)
		gettext-envsubst && \
    rm /usr/share/nmap/nmap-os-db \
       /usr/share/nmap/nselib/data/wp-plugins.lst \
       /usr/share/nmap/nselib/data/wp-themes.lst \
       /usr/share/nmap/nselib/data/drupal-modules.lst && \
    upx --lzma \
        /sbin/ip \
        /usr/bin/nmap  \
        /usr/bin/coreutils  \
        /usr/bin/openssl  \
        /usr/bin/socat  \
        /usr/bin/top  \
        /usr/bin/curl \
        /usr/bin/envsubst \
        /usr/sbin/openvpn && \
    apk del --no-cache upx

COPY --link --from=agent-builder /usr/bin/docker /usr/bin/docker
COPY --link --from=agent-builder /usr/local/libexec/docker/cli-plugins/docker-compose \
                                 /usr/local/libexec/docker/cli-plugins/docker-compose
RUN ln -s /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose
COPY --link --from=agent-builder /usr/local/bin/kubectl /usr/local/bin/kubectl
COPY --link --from=agent-builder /usr/local/bin/helm /usr/local/bin/helm

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


# Peripheral discovery: ModBus
RUN mkdir -p /usr/share/nmap/scripts/
COPY --link --from=modbus-builder /usr/share/nmap/scripts/modbus-discover.nse /usr/share/nmap/scripts/modbus-discover.nse


# Security module
# nmap nmap-scripts coreutils curl
COPY --link nuvlaedge/security/patch/vulscan.nse /usr/share/nmap/scripts/vulscan/
COPY --link nuvlaedge/security/security-entrypoint.sh /usr/bin/security-entrypoint


# Compute API
COPY scripts/compute-api/api.sh /usr/bin/api


# VPN Client
COPY --link scripts/vpn-client/* /opt/nuvlaedge/scripts/vpn-client/
RUN mv /opt/nuvlaedge/scripts/vpn-client/openvpn-client.sh /usr/bin/openvpn-client && \
    # For backward compatibility with existing vpn/nuvlaedge.conf file
    ln -s /opt/nuvlaedge/scripts/vpn-client/get_ip.sh /opt/nuvlaedge/scripts/get_ip.sh && \
    ln -s /opt/nuvlaedge/scripts/vpn-client/wait-for-vpn-update.sh /opt/nuvlaedge/scripts/wait-for-vpn-update.sh


# Kubernetes credential manager
COPY --link scripts/credential-manager/* /opt/nuvlaedge/scripts/credential-manager/
RUN cp /opt/nuvlaedge/scripts/credential-manager/kubernetes-credential-manager.sh /usr/bin/kubernetes-credential-manager


# Give execution permission
RUN chmod +x \
    # Security
    /usr/bin/security-entrypoint \
    # Compute API
    /usr/bin/api \
    # VPN client
    /usr/bin/openvpn-client \
    /opt/nuvlaedge/scripts/vpn-client/get_ip.sh \
    /opt/nuvlaedge/scripts/vpn-client/wait-for-vpn-update.sh \
    # Kubernetes credential manager
    /usr/bin/kubernetes-credential-manager

# Configuration files
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
