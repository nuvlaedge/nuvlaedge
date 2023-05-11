ARG BASE_IMAGE=python:3.11-alpine3.17
FROM ${BASE_IMAGE} AS pyopenssl-builder

RUN apk update
RUN apk update --no-cache curl

RUN curl -sSL https://install.python-poetry.org | python3 -

VOLUME /etc/nuvlaedge/database

COPY nuvlaedge /opt/nuvlaedge

WORKDIR /opt/nuvlaedge
