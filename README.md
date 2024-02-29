# NuvlaEdge

[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg?style=for-the-badge)](https://github.com/nuvlaedge/nuvlaedge/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/nuvlaedge/nuvlaedge?style=for-the-badge&logo=github&logoColor=white)](https://GitHub.com/nuvlaedge/nuvlaedge/issues/)
[![GitHub release](https://img.shields.io/github/release/nuvlaedge/nuvlaedge?style=for-the-badge&logo=github&logoColor=white)](https://github.com/nuvlaedge/nuvlaedge/releases/tag/1.1.0)
[![GitHub release](https://img.shields.io/github/release-date/nuvlaedge/nuvlaedge?logo=github&logoColor=white&style=for-the-badge)](https://github.com/nuvlaedge/nuvlaedge/releases)


This repository contains the NuvlaEdge source code, a microservice based agent for [Nuvla.io](https://nuvla.io).
NuvlaEdge consists in the following services:
- **Agent**: Main NuvlaEdge component that implements the Nuvla protocol, gathers system configuration and statistics and 
runs jobs from Nuvla.
- **System Manager**: NuvlaEdge watchdog component. Monitors the different microservices and heals them if they fail.
- **Peripherals**: NuvlaEdge add-ons that allows the detection of differnt types of devices:
  - Network
  - Bluetooth
  - USB
  - Modbus
  - GPU


For installation instructions, read the [online documentation](https://docs.nuvla.io/nuvlaedge/installation/).


## Latest releases and artifacts

| repository                                                            | release                                                                                                                                                                                                | artifact                                                                                                                                                                                                              |
|-----------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [NuvlaEdge (deployment)](https://github.com/nuvlaedge/deployment)     | [![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/nuvlaedge/deployment?label=version&sort=semver&style=flat-square)](https://github.com/nuvlaedge/deployment)                         |                                                                                                                                                                                                                       |
| [NuvlaEdge](https://github.com/nuvlaedge/nuvlaedge)                   | [![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/nuvlaedge/nuvlaedge?label=version&sort=semver&style=flat-square)](https://github.com/nuvlaedge/nuvlaedge)                           | [![Docker Image Version (latest semver)](https://img.shields.io/docker/v/nuvlaedge/nuvlaedge?label=image&sort=semver&style=flat-square)](https://hub.docker.com/r/nuvlaedge/nuvlaedge/tags)                           |


## Build Status

To get more information on the latest builds click on the build status badges below.

| repository                                                            | status                                                                                                                                                                                                                                                                                                                                                                                         |
|-----------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [NuvlaEdge (deployment)](https://github.com/nuvlaedge/deployment)     | [![Build Status](https://github.com/nuvlaedge/deployment/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/nuvlaedge/deployment/actions/workflows/main.yml) <br> [![Build Status](https://github.com/nuvlaedge/deployment/actions/workflows/integration-tests.yml/badge.svg?branch=main)](https://github.com/nuvlaedge/deployment/actions/workflows/integration-tests.yml) |
| [NuvlaEdge](https://github.com/nuvlaedge/nuvlaedge)                   | [![Build Status](https://github.com/nuvlaedge/nuvlaedge/actions/workflows/build-main-devel.yml/badge.svg?branch=main)](https://github.com/nuvlaedge/nuvlaedge/actions/workflows/build-main-devel.yml)                                                                                                                                                                                          |
| [Job Engine](https://github.com/nuvla/job-engine)                     | [![Build Status](https://github.com/nuvla/job-engine/actions/workflows/release.yml/badge.svg?branch=master)](https://github.com/nuvla/job-engine/actions/workflows/release.yml)                                                                                                                                                                                                                |


## Project tools

The project uses [poetry](https://python-poetry.org/)
for the project and dependency management and [tox](https://tox.wiki/en/latest/)
for tests execution and results reporting.

### Running unit tests

Before running unit tests with `tox` you need to generate requirements file out
of the per-component dependency lists provided in the `poetry`'s project
definition file.

For that run the following wrapper script:

```shell
./generate-requiremenents.sh
```

Then run the unit tests with:

```shell
tox
```

## Copyright

Copyright &copy; 2024, SixSq SA

## License

Licensed under the Apache License, Version 2.0 (the "License"); you
may not use this file except in compliance with the License.  You may
obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
implied.  See the License for the specific language governing
permissions and limitations under the License.
