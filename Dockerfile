ARG BASE_IMAGE=python:3.11-alpine3.17
FROM ${BASE_IMAGE} AS nuvlaedge-builder

RUN apk update
RUN apk add --no-cache curl libffi-dev gcc musl-dev

COPY dist/nuvlaedge-0.1.0-py3-none-any.whl /tmp/
RUN pip install /tmp/nuvlaedge-0.1.0-py3-none-any.whl


FROM ${BASE_IMAGE}
COPY --from=nuvlaedge-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=nuvlaedge-builder /usr/local/bin /usr/local/bin

VOLUME /etc/nuvlaedge/database

#COPY nuvlaedge/ /opt/nuvlaedge/
COPY pyproject.toml /opt/
COPY poetry.lock /opt/
COPY README.md /opt/

WORKDIR /opt/

