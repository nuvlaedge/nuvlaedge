ARG BASE_IMAGE=nuvladev/nuvlaedge-base:latest
FROM ${BASE_IMAGE}

RUN apk --no-cache add iproute2

ENTRYPOINT ["ip"]
