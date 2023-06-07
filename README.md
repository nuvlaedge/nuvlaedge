# NuvlaEdge

[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg?style=for-the-badge)](https://github.com/nuvlaedge/nuvlaedge/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/nuvlaedge/nuvlaedge?style=for-the-badge&logo=github&logoColor=white)](https://GitHub.com/nuvlaedge/nuvlaedge/issues/)
[![GitHub release](https://img.shields.io/github/release/nuvlaedge/nuvlaedge?style=for-the-badge&logo=github&logoColor=white)](https://github.com/nuvlaedge/nuvlaedge/releases/tag/1.1.0)
[![GitHub release](https://img.shields.io/github/release-date/nuvlaedge/nuvlaedge?logo=github&logoColor=white&style=for-the-badge)](https://github.com/nuvlaedge/nuvlaedge/releases)


This repository contains the main NuvlaEdge source code, a microservice based agent for [Nuvla.io](https://nuvla.io).
NuvlaEdge consists in the following services:
- **Agent**: Main NuvlaEdge component that implements the Nuvla protocol, gathers system configuration and statistics and 
runs jobs from Nuvla.
- **System Manager**: NuvlaEdge watchdog component. Monitors the different microservices and heals them if they fail.
- **Peripherals**: NuvlaEdge add-ons that allows the detection of differnt types of devices:
  - Network scan
  - Bluetooth
  - USB
  - Modbus
  - GPU. Hosted on its own [repository](https://github.com/nuvlaedge/peripheral-manager-gpu)


For installation instructions, read the [online documentation](https://docs.nuvla.io/nuvlaedge/nuvlaedge-engine/).


## Latest releases and artifacts

| repository                                                            | release                                                                                                                                                                                                | artifact                                                                                                                                                                                                              |
|-----------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [NuvlaEdge (deployment)](https://github.com/nuvlaedge/deployment)     | [![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/nuvlaedge/deployment?label=version&sort=semver&style=flat-square)](https://github.com/nuvlaedge/deployment)                         |                                                                                                                                                                                                                       |
| [NuvlaEdge](https://github.com/nuvlaedge/nuvlaedge)                   | [![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/nuvlaedge/nuvlaedge?label=version&sort=semver&style=flat-square)](https://github.com/nuvlaedge/nuvlaedge)                           | [![Docker Image Version (latest semver)](https://img.shields.io/docker/v/nuvlaedge/nuvlaedge?label=image&sort=semver&style=flat-square)](https://hub.docker.com/r/nuvlaedge/nuvlaedge/tags)                           |
| [Compute API](https://github.com/nuvlaedge/compute-api)               | [![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/nuvlaedge/compute-api?label=version&sort=semver&style=flat-square)](https://github.com/nuvlaedge/compute-api)                       | [![Docker Image Version (latest semver)](https://img.shields.io/docker/v/nuvlaedge/compute-api?label=image&sort=semver&style=flat-square)](https://hub.docker.com/r/nuvlaedge/compute-api/tags)                       |
| [VPN Client](https://github.com/nuvlaedge/vpn-client)                 | [![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/nuvlaedge/vpn-client?label=version&sort=semver&style=flat-square)](https://github.com/nuvlaedge/vpn-client)                         | [![Docker Image Version (latest semver)](https://img.shields.io/docker/v/nuvlaedge/vpn-client?label=image&sort=semver&style=flat-square)](https://hub.docker.com/r/nuvlaedge/vpn-client/tags)                         |
| [Job Engine](https://github.com/nuvla/job-engine)                     | [![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/nuvla/job-engine?label=version&sort=semver&style=flat-square)](https://github.com/nuvla/job-engine)                                 | [![Docker Image Version (latest semver)](https://img.shields.io/docker/v/nuvla/job-lite?label=image&sort=semver&style=flat-square)](https://hub.docker.com/r/nuvla/job-lite/tags)                                     |
| [Security](https://github.com/nuvlaedge/security)                     | [![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/nuvlaedge/security?label=version&sort=semver&style=flat-square)](https://github.com/nuvlaedge/security)                             | [![Docker Image Version (latest semver)](https://img.shields.io/docker/v/nuvlaedge/security?label=image&sort=semver&style=flat-square)](https://hub.docker.com/r/nuvlaedge/security/tags)                             |
| [GPU Peripheral](https://github.com/nuvlaedge/peripheral-manager-gpu) | [![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/nuvlaedge/peripheral-manager-gpu?label=version&sort=semver&style=flat-square)](https://github.com/nuvlaedge/peripheral-manager-gpu) | [![Docker Image Version (latest semver)](https://img.shields.io/docker/v/nuvlaedge/peripheral-manager-gpu?label=image&sort=semver&style=flat-square)](https://hub.docker.com/r/nuvlaedge/peripheral-manager-gpu/tags) |

## Build Status

To get more information on the latest builds click on the build status badges below.

| repository                                                            | status                                                                                                                                                                                                                                                                                                                                                                                         |
|-----------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [NuvlaEdge (deployment)](https://github.com/nuvlaedge/deployment)     | [![Build Status](https://github.com/nuvlaedge/deployment/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/nuvlaedge/deployment/actions/workflows/main.yml) <br> [![Build Status](https://github.com/nuvlaedge/deployment/actions/workflows/integration-tests.yml/badge.svg?branch=main)](https://github.com/nuvlaedge/deployment/actions/workflows/integration-tests.yml) |
| [NuvlaEdge](https://github.com/nuvlaedge/nuvlaedge)                   | [![Build Status](https://github.com/nuvlaedge/nuvlaedge/actions/workflows/build-main-devel.yml/badge.svg?branch=main)](https://github.com/nuvlaedge/nuvlaedge/actions/workflows/build-main-devel.yml)                                                                                                                                                                                          |
| [Compute API](https://github.com/nuvlaedge/compute-api)               | [![Build Status](https://github.com/nuvlaedge/compute-api/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/nuvlaedge/compute-api/actions/workflows/main.yml)                                                                                                                                                                                                              |
| [VPN Client](https://github.com/nuvlaedge/vpn-client)                 | [![Build Status](https://github.com/nuvlaedge/vpn-client/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/nuvlaedge/vpn-client/actions/workflows/main.yml)                                                                                                                                                                                                                |
| [Job Engine](https://github.com/nuvla/job-engine)                     | [![Build Status](https://github.com/nuvla/job-engine/actions/workflows/main.yml/badge.svg?branch=master)](https://github.com/nuvla/job-engine/actions/workflows/main.yml)                                                                                                                                                                                                                      |
| [Security](https://github.com/nuvlaedge/security)                     | [![Build Status](https://github.com/nuvlaedge/security/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/nuvlaedge/security/actions/workflows/main.yml)                                                                                                                                                                                                                    |
| [GPU Peripheral](https://github.com/nuvlaedge/peripheral-manager-gpu) | [![Build Status](https://github.com/nuvlaedge/peripheral-manager-gpu/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/nuvlaedge/peripheral-manager-gpu/actions/workflows/main.yml)                                                                                                                                                                                        |

## Copyright

Copyright &copy; 2023, SixSq SA

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
