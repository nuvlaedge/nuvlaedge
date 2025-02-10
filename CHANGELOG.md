# Changelog

## [2.18.0](https://github.com/nuvlaedge/nuvlaedge/compare/2.17.1...2.18.0) (2024-12-20)


### Features

* **job:** authenticate to Nuvla with cookies when starting job engine container ([#214](https://github.com/nuvlaedge/nuvlaedge/issues/214)) ([6887e61](https://github.com/nuvlaedge/nuvlaedge/commit/6887e61e1b1893b2577393d2a825f1fbc386437c))
* **kubernetes-credential-manager:** by default use NE UUID in CSR name to support multiple NEs on k8s cluster ([#227](https://github.com/nuvlaedge/nuvlaedge/issues/227)) ([53d5db8](https://github.com/nuvlaedge/nuvlaedge/commit/53d5db8ab3b82f8ac6248b2e960e49326aa622c6))
* **kubernetes:** add support for listing Helm releases ([#225](https://github.com/nuvlaedge/nuvlaedge/issues/225)) ([3629076](https://github.com/nuvlaedge/nuvlaedge/commit/362907612c0b8ad918f50cb3fea479432d0cc1b7))
* **telemetry:** add raw coe resources for kubernetes ([#216](https://github.com/nuvlaedge/nuvlaedge/issues/216)) ([fa39833](https://github.com/nuvlaedge/nuvlaedge/commit/fa3983327e0033f8be37acbbe567205805273f60))


### Bug Fixes

* **kubernetes:** $CSR_NAME badly provided to wait for issued certificate ([53d5db8](https://github.com/nuvlaedge/nuvlaedge/commit/53d5db8ab3b82f8ac6248b2e960e49326aa622c6))
* **agent:** don't fail in case same job is requested to be started ([#230](https://github.com/nuvlaedge/nuvlaedge/issues/230)) ([28a2ad5](https://github.com/nuvlaedge/nuvlaedge/commit/28a2ad50a2c366a6251388672ef385073cd9dbbf))
* **agent:** fix status handler bugs ([#228](https://github.com/nuvlaedge/nuvlaedge/issues/228)) ([fdb487d](https://github.com/nuvlaedge/nuvlaedge/commit/fdb487d4d2c3512a7d117955ac053db722bc1464))
* **agent:** filtering out sensitive fields when logging VPN related informations ([#222](https://github.com/nuvlaedge/nuvlaedge/issues/222)) ([eff57a1](https://github.com/nuvlaedge/nuvlaedge/commit/eff57a19441d53825bb7d9d2365ae3509c44ab18))
* **kubernetes:** detect manager nodes on new and old clusters ([#231](https://github.com/nuvlaedge/nuvlaedge/issues/231)) ([8c374c1](https://github.com/nuvlaedge/nuvlaedge/commit/8c374c1912c9b5008d521158a6d83ee702e0800d))
* **telemetry:** send disk usage and capacity in bytes ([#233](https://github.com/nuvlaedge/nuvlaedge/issues/233)) ([cdce9ec](https://github.com/nuvlaedge/nuvlaedge/commit/cdce9ec20af846a2402fb5116f55dc3bf4ffa5ea))


### Dependencies

* nuvla-api ^4.2.3 ([6aa05bb](https://github.com/nuvlaedge/nuvlaedge/commit/6aa05bb06a8ac2e1b4319149626f6af30723473c))
* nuvla-job-engine ^4.9.0 ([13fc256](https://github.com/nuvlaedge/nuvlaedge/commit/13fc256baf2c9d8b1424c1e861b54138b07d87be))
* updated indirect dependencies ([13fc256](https://github.com/nuvlaedge/nuvlaedge/commit/13fc256baf2c9d8b1424c1e861b54138b07d87be))


### Code Refactoring

* **telemetry:** docker: improved collection of containers stats ([#232](https://github.com/nuvlaedge/nuvlaedge/issues/232)) ([807f25e](https://github.com/nuvlaedge/nuvlaedge/commit/807f25eb4474ae99fe36ced06edd216e65d28f92))
* **telemetry:** minor improvements ([#226](https://github.com/nuvlaedge/nuvlaedge/issues/226)) ([7c7c95b](https://github.com/nuvlaedge/nuvlaedge/commit/7c7c95b3f1be615d348eb30d30a8f68b94345f7c))


## [2.17.1](https://github.com/nuvlaedge/nuvlaedge/compare/2.17.0...2.17.1) (2024-11-02)


### Bug Fixes

* **agent:** fix an issue with irs loading on some platforms ([#217](https://github.com/nuvlaedge/nuvlaedge/issues/217)) ([862ce13](https://github.com/nuvlaedge/nuvlaedge/commit/862ce135888767ff2974b2518fb1439cf7d6ee82))
* **agent:** send installation-parameters even if partial ([#209](https://github.com/nuvlaedge/nuvlaedge/issues/209)) ([f0992ae](https://github.com/nuvlaedge/nuvlaedge/commit/f0992ae40195fe2cbcf8f62d6ba58a8be6af3ebb))
* **telemetry:** fixes and improvements to telemetry ([#215](https://github.com/nuvlaedge/nuvlaedge/issues/215)) ([65b41fd](https://github.com/nuvlaedge/nuvlaedge/commit/65b41fd07be12c78851d6556661aed49dc9a88dc))


### Continuous Integration

* (release-please): fix upload of assets in release ([72fd227](https://github.com/nuvlaedge/nuvlaedge/commit/72fd22781f6a34f3bf5fe65957a2bbfacfb50338))
* add workflow manual-release.yml ([63dd40a](https://github.com/nuvlaedge/nuvlaedge/commit/63dd40ac1357f60a5cf5d540c4bb56261d81067d))
* **release-please:** fix version number and docker images tag ([21efa96](https://github.com/nuvlaedge/nuvlaedge/commit/21efa961350cff3205aa2bb8c1c51b62ebe4f321))
* replace release workflow with release-please action ([#210](https://github.com/nuvlaedge/nuvlaedge/issues/210)) ([4e09af5](https://github.com/nuvlaedge/nuvlaedge/commit/4e09af5f934d82122c6413f3ab7237f03c025db6))

## [2.16.2](https://github.com/nuvlaedge/nuvlaedge/compare/2.16.1...2.16.2) (2024-11-02)

### Bug Fixes

* **agent:** fix an issue with irs loading on some platforms (backport of [#217](https://github.com/nuvlaedge/nuvlaedge/issues/217)) (original commit: [862ce13](https://github.com/nuvlaedge/nuvlaedge/commit/862ce135888767ff2974b2518fb1439cf7d6ee82))
* **telemetry:** fixes and improvements to telemetry (backport of [#215](https://github.com/nuvlaedge/nuvlaedge/issues/215)) (original commit: [65b41fd](https://github.com/nuvlaedge/nuvlaedge/commit/65b41fd07be12c78851d6556661aed49dc9a88dc))
* use our own compose binary in the slim-docker image (backport) (original commit: [7322d3f](https://github.com/nuvlaedge/nuvlaedge/commit/7322d3f5363e7d340140e2654025080f76548f82))

## [2.16.1](https://github.com/nuvlaedge/nuvlaedge/tree/2.16.1) (2024-09-30)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.16.0...2.16.1)

## [2.16.0](https://github.com/nuvlaedge/nuvlaedge/tree/2.16.0) (2024-09-27)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.15.3...2.16.0)

**Merged pull requests:**

- feat: slim version of docker image … [\#200](https://github.com/nuvlaedge/nuvlaedge/pull/200) ([schaubl](https://github.com/schaubl))
- Cred encryption [\#199](https://github.com/nuvlaedge/nuvlaedge/pull/199) ([schaubl](https://github.com/schaubl))
- fix: update collect\_container\_metrics\(\) to support old\_version parameter in K8s driver [\#198](https://github.com/nuvlaedge/nuvlaedge/pull/198) ([konstan](https://github.com/konstan))
- feat\(telemetry\): add raw coe resources [\#197](https://github.com/nuvlaedge/nuvlaedge/pull/197) ([schaubl](https://github.com/schaubl))
- feat\(telemetry\): wip use json patch for telemetry [\#196](https://github.com/nuvlaedge/nuvlaedge/pull/196) ([schaubl](https://github.com/schaubl))
- fix\(docker.py\): fix retrieval of current container id via mountinfo [\#195](https://github.com/nuvlaedge/nuvlaedge/pull/195) ([schaubl](https://github.com/schaubl))

## [2.15.3](https://github.com/nuvlaedge/nuvlaedge/tree/2.15.3) (2024-08-27)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.15.2...2.15.3)

## [2.15.2](https://github.com/nuvlaedge/nuvlaedge/tree/2.15.2) (2024-08-21)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.15.1...2.15.2)

**Merged pull requests:**

- fix\(container\_stats\): properly detect if Nuvla support new container stats [\#194](https://github.com/nuvlaedge/nuvlaedge/pull/194) ([schaubl](https://github.com/schaubl))

## [2.15.1](https://github.com/nuvlaedge/nuvlaedge/tree/2.15.1) (2024-08-05)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.15.0...2.15.1)

**Merged pull requests:**

- fix\(job\_local\): fix issues when running job in agent [\#193](https://github.com/nuvlaedge/nuvlaedge/pull/193) ([schaubl](https://github.com/schaubl))

## [2.15.0](https://github.com/nuvlaedge/nuvlaedge/tree/2.15.0) (2024-07-21)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.14.4...2.15.0)

**Merged pull requests:**

- deps: get docker compose from our own build [\#192](https://github.com/nuvlaedge/nuvlaedge/pull/192) ([schaubl](https://github.com/schaubl))
- refactor\(agent\): improve jobs execution in agent … [\#191](https://github.com/nuvlaedge/nuvlaedge/pull/191) ([schaubl](https://github.com/schaubl))
- Container stats [\#189](https://github.com/nuvlaedge/nuvlaedge/pull/189) ([amitbhanja](https://github.com/amitbhanja))
- Job execution in agent [\#187](https://github.com/nuvlaedge/nuvlaedge/pull/187) ([schaubl](https://github.com/schaubl))
- agent: get IPs with network\_mode=host and allow data-gateway without system-manager [\#186](https://github.com/nuvlaedge/nuvlaedge/pull/186) ([schaubl](https://github.com/schaubl))
- fix: Add thread tracer on signal SIGUSR1 [\#185](https://github.com/nuvlaedge/nuvlaedge/pull/185) ([ignacio-penas](https://github.com/ignacio-penas))

## [2.14.4](https://github.com/nuvlaedge/nuvlaedge/tree/2.14.4) (2024-05-27)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.14.3...2.14.4)

**Merged pull requests:**

- actions: update actions dependencies [\#184](https://github.com/nuvlaedge/nuvlaedge/pull/184) ([schaubl](https://github.com/schaubl))
- fix: Fix requests dependency to 2.31.0 since 2.32.X causes incompatibility issues with docker library [\#183](https://github.com/nuvlaedge/nuvlaedge/pull/183) ([ignacio-penas](https://github.com/ignacio-penas))
- fix: Agent logging env configuration [\#182](https://github.com/nuvlaedge/nuvlaedge/pull/182) ([ignacio-penas](https://github.com/ignacio-penas))
- feat: add script docker-prune allowing to periodically cleanup docker resources [\#181](https://github.com/nuvlaedge/nuvlaedge/pull/181) ([schaubl](https://github.com/schaubl))
- fix\(client\_wrapper.py\): Re-enable compression of data sent to Nuvla [\#180](https://github.com/nuvlaedge/nuvlaedge/pull/180) ([schaubl](https://github.com/schaubl))

## [2.14.3](https://github.com/nuvlaedge/nuvlaedge/tree/2.14.3) (2024-05-15)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.14.2...2.14.3)

**Merged pull requests:**

- Fix bugs from v2.14.1 [\#174](https://github.com/nuvlaedge/nuvlaedge/pull/174) ([ignacio-penas](https://github.com/ignacio-penas))

## [2.14.2](https://github.com/nuvlaedge/nuvlaedge/tree/2.14.2) (2024-05-08)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.14.1...2.14.2)

**Fixed bugs:**

- fix(Dockerfile): pydantic version specification

**Merged pull requests:**

- fix: fix bugs introduced in k8s NuvlaEdge (#172)
- fix: remove authenticated check in heartbeat loop. (#169)
- Fix insecure flag bug (#170)
- deps: rename frozen session data structure verify into session (#171)
- fix: error on building pydantic for ARM32Add. adds nuvlaedge base image as a GH package (#168)
- Fixed HOST_HOME and add settings unittests (#166)

## [2.14.1](https://github.com/nuvlaedge/nuvlaedge/tree/2.14.1) (2024-04-10)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.14.0...2.14.1)

**Implemented enhancements:**

- Update job-engine to 4.0.4

**Fixed bugs:**

- fix(agent): fix NUVLAEDGE_IMMUTABLE_SSH_PUB_KEY env var name

**Merged pull requests:**

- Improved Settings and NuvlaEdge UUID retrival [\#165](https://github.com/nuvlaedge/nuvlaedge/pull/165) ([ignacio-penas](https://github.com/ignacio-penas))

## [2.14.0](https://github.com/nuvlaedge/nuvlaedge/tree/2.14.0) (2024-04-03)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.13.2...2.14.0)

**Merged pull requests:**

- fix: adds a prebuild version of pydantic from Alpine edge repo. [\#164](https://github.com/nuvlaedge/nuvlaedge/pull/164) ([ignacio-penas](https://github.com/ignacio-penas))
- Add nuvla-job-engine package to requirements to install job-engine tools [\#158](https://github.com/nuvlaedge/nuvlaedge/pull/158) ([ignacio-penas](https://github.com/ignacio-penas))
- Refactor nuvlaedge common and agent [\#150](https://github.com/nuvlaedge/nuvlaedge/pull/150) ([ignacio-penas](https://github.com/ignacio-penas))

## [2.13.2](https://github.com/nuvlaedge/nuvlaedge/tree/2.13.2) (2024-04-02)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.13.1...2.13.2)

**Merged pull requests:**

- agent telemetry: fix network interfaces not removed [\#163](https://github.com/nuvlaedge/nuvlaedge/pull/163) ([schaubl](https://github.com/schaubl))
- ci: add local build script [\#162](https://github.com/nuvlaedge/nuvlaedge/pull/162) ([ignacio-penas](https://github.com/ignacio-penas))
- docs: fix job-engine build workflow link in README.md [\#159](https://github.com/nuvlaedge/nuvlaedge/pull/159) ([ignacio-penas](https://github.com/ignacio-penas))

## [2.13.1](https://github.com/nuvlaedge/nuvlaedge/tree/2.13.1) (2024-02-16)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.13.0...2.13.1)

**Merged pull requests:**

- Make the csr and cluster role naming bindings unique [\#156](https://github.com/nuvlaedge/nuvlaedge/pull/156) ([giovannibianco](https://github.com/giovannibianco))

## [2.13.0](https://github.com/nuvlaedge/nuvlaedge/tree/2.13.0) (2023-12-16)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.12.2...2.13.0)

**Implemented enhancements:**

- Set pull-always for images in Kubernetes via environment variables. [\#132](https://github.com/nuvlaedge/nuvlaedge/issues/132)
- Set the image pull policy [\#142](https://github.com/nuvlaedge/nuvlaedge/pull/142) ([giovannibianco](https://github.com/giovannibianco))

**Merged pull requests:**

- Handle Dbus Error for ble [\#148](https://github.com/nuvlaedge/nuvlaedge/pull/148) ([amitbhanja](https://github.com/amitbhanja))
- Added retry system for TimedActions [\#144](https://github.com/nuvlaedge/nuvlaedge/pull/144) ([ignacio-penas](https://github.com/ignacio-penas))
- Dockerfile refactor: reduce Docker image size and number of layers [\#143](https://github.com/nuvlaedge/nuvlaedge/pull/143) ([schaubl](https://github.com/schaubl))

## [2.12.2](https://github.com/nuvlaedge/nuvlaedge/tree/2.12.2) (2023-11-16)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.12.1...2.12.2)

**Fixed bugs:**

- Update the list of components for kubernetes NE deployments [\#130](https://github.com/nuvlaedge/nuvlaedge/issues/130)
- Get the component list for the deployment of a Kubernetes NE [\#131](https://github.com/nuvlaedge/nuvlaedge/pull/131) ([giovannibianco](https://github.com/giovannibianco))

**Merged pull requests:**

- Refactor and bugfixes [\#140](https://github.com/nuvlaedge/nuvlaedge/pull/140) ([schaubl](https://github.com/schaubl))

## [2.12.1](https://github.com/nuvlaedge/nuvlaedge/tree/2.12.1) (2023-11-05)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.12.0...2.12.1)

**Implemented enhancements:**

- Bluetooth peripheral discovery: add support for BLE device discovery [\#123](https://github.com/nuvlaedge/nuvlaedge/issues/123)

**Fixed bugs:**

- Add a time-to-live to the kubernetes-credential manager [\#134](https://github.com/nuvlaedge/nuvlaedge/issues/134)

**Merged pull requests:**

- Exception Check for BLE devices [\#137](https://github.com/nuvlaedge/nuvlaedge/pull/137) ([amitbhanja](https://github.com/amitbhanja))
- Minor changes for BLE [\#136](https://github.com/nuvlaedge/nuvlaedge/pull/136) ([amitbhanja](https://github.com/amitbhanja))
- Fix validation workflow [\#135](https://github.com/nuvlaedge/nuvlaedge/pull/135) ([ignacio-penas](https://github.com/ignacio-penas))
- Fix the modbus detection from kubernetes NuvlaEdge [\#116](https://github.com/nuvlaedge/nuvlaedge/pull/116) ([giovannibianco](https://github.com/giovannibianco))

## [2.12.0](https://github.com/nuvlaedge/nuvlaedge/tree/2.12.0) (2023-10-31)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.11.2...2.12.0)

**Implemented enhancements:**

- Bluetooth peripheral discovery: add support for BLE device discovery [\#123](https://github.com/nuvlaedge/nuvlaedge/issues/123)
- feat\(agent\): Use the new heartbeat operation of the api-server [\#88](https://github.com/nuvlaedge/nuvlaedge/issues/88)
- feat\(agent\): Add heartbeat operation [\#117](https://github.com/nuvlaedge/nuvlaedge/pull/117) ([ignacio-penas](https://github.com/ignacio-penas))

**Closed issues:**

- NE on K8s: validate peripheral discovery works on K8s [\#81](https://github.com/nuvlaedge/nuvlaedge/issues/81)
- feat\(agent\): Execute jobs returned by the server even if the telemetry update request failed server-side [\#91](https://github.com/nuvlaedge/nuvlaedge/issues/91)

**Merged pull requests:**

- Added exception catch to prevent errors from faulty server responses [\#129](https://github.com/nuvlaedge/nuvlaedge/pull/129) ([ignacio-penas](https://github.com/ignacio-penas))
- Improved thread handling in telemetry class [\#128](https://github.com/nuvlaedge/nuvlaedge/pull/128) ([ignacio-penas](https://github.com/ignacio-penas))
- Adding ble support [\#125](https://github.com/nuvlaedge/nuvlaedge/pull/125) ([amitbhanja](https://github.com/amitbhanja))

## [2.11.2](https://github.com/nuvlaedge/nuvlaedge/tree/2.11.2) (2023-10-02)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.11.1...2.11.2)

## [2.11.1](https://github.com/nuvlaedge/nuvlaedge/tree/2.11.1) (2023-09-26)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.11.0...2.11.1)

**Implemented enhancements:**

- Refarctor Mod bus XML parser [\#121](https://github.com/nuvlaedge/nuvlaedge/issues/121)

**Merged pull requests:**

- Support for fixing the update mechanism for kubernetes deployed Nuvlaedges [\#124](https://github.com/nuvlaedge/nuvlaedge/pull/124) ([giovannibianco](https://github.com/giovannibianco))
- Refractor Modbus XML Parser [\#122](https://github.com/nuvlaedge/nuvlaedge/pull/122) ([amitbhanja](https://github.com/amitbhanja))

## [2.11.0](https://github.com/nuvlaedge/nuvlaedge/tree/2.11.0) (2023-09-05)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.10.4...2.11.0)

**Implemented enhancements:**

- Update docker-compose usage to compose V2 [\#115](https://github.com/nuvlaedge/nuvlaedge/issues/115)
- feat: integrate vulnerabilities scan module  [\#107](https://github.com/nuvlaedge/nuvlaedge/issues/107)
- feat: Add support for validation log retrieval as artefacts [\#105](https://github.com/nuvlaedge/nuvlaedge/issues/105)
- rename container runtime to container orchestration engine [\#98](https://github.com/nuvlaedge/nuvlaedge/issues/98)
- integrate k8s cred manager into nuvlaedge/nuvlaedge repo [\#76](https://github.com/nuvlaedge/nuvlaedge/issues/76)
- address TODOs and FIXMEs in the code [\#68](https://github.com/nuvlaedge/nuvlaedge/issues/68)
- Merge security component [\#108](https://github.com/nuvlaedge/nuvlaedge/pull/108) ([ignacio-penas](https://github.com/ignacio-penas))
- Add validation logs retrieval. Validation release 1.2.0 [\#106](https://github.com/nuvlaedge/nuvlaedge/pull/106) ([ignacio-penas](https://github.com/ignacio-penas))
- feat: Validation workflow refactor [\#102](https://github.com/nuvlaedge/nuvlaedge/pull/102) ([ignacio-penas](https://github.com/ignacio-penas))
- Add credentials to the job engine Job specification [\#86](https://github.com/nuvlaedge/nuvlaedge/pull/86) ([giovannibianco](https://github.com/giovannibianco))

**Fixed bugs:**

- Security Dataclass parsing bug [\#119](https://github.com/nuvlaedge/nuvlaedge/issues/119)
- \[Bug\] ModBus not reporting discovered device [\#111](https://github.com/nuvlaedge/nuvlaedge/issues/111)
- \[Fix\] Validation not working due to version mismatch [\#100](https://github.com/nuvlaedge/nuvlaedge/issues/100)
- \[BUG\] on k8s adding ssh key doesn't work because docker driver is used [\#83](https://github.com/nuvlaedge/nuvlaedge/issues/83)
- Fixes modbus discovery [\#112](https://github.com/nuvlaedge/nuvlaedge/pull/112) ([ignacio-penas](https://github.com/ignacio-penas))
- fix: Dockerfile fix for cython 3.0.0 release on PyYaml dependency [\#103](https://github.com/nuvlaedge/nuvlaedge/pull/103) ([ignacio-penas](https://github.com/ignacio-penas))

**Closed issues:**

- Deleting ssh key does not work [\#109](https://github.com/nuvlaedge/nuvlaedge/issues/109)
- K8s: investigate generic-device-plugin for discovery and allocation of devices to containers on K8s at the edge [\#82](https://github.com/nuvlaedge/nuvlaedge/issues/82)

**Merged pull requests:**

- Fix dataclass json serialization [\#118](https://github.com/nuvlaedge/nuvlaedge/pull/118) ([ignacio-penas](https://github.com/ignacio-penas))
- Removed old docker-compose v1 and job executors improvements [\#113](https://github.com/nuvlaedge/nuvlaedge/pull/113) ([ignacio-penas](https://github.com/ignacio-penas))
- Merge credentials manager [\#110](https://github.com/nuvlaedge/nuvlaedge/pull/110) ([ignacio-penas](https://github.com/ignacio-penas))
- rename: Docker and Kubernetes are not CR but COE [\#99](https://github.com/nuvlaedge/nuvlaedge/pull/99) ([konstan](https://github.com/konstan))
- fix: remove outdated TODOS and move relevant ones into issues [\#70](https://github.com/nuvlaedge/nuvlaedge/pull/70) ([ignacio-penas](https://github.com/ignacio-penas))

## [2.10.4](https://github.com/nuvlaedge/nuvlaedge/tree/2.10.4) (2023-07-16)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.10.3...2.10.4)

**Merged pull requests:**

- fix\(agent\): commission infrastructure-service and its credential even without compute-api [\#101](https://github.com/nuvlaedge/nuvlaedge/pull/101) ([schaubl](https://github.com/schaubl))

## [2.10.3](https://github.com/nuvlaedge/nuvlaedge/tree/2.10.3) (2023-07-04)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.10.2...2.10.3)

**Fixed bugs:**

- \[Bug\] Peripherals not reporting names properly [\#53](https://github.com/nuvlaedge/nuvlaedge/issues/53)

## [2.10.2](https://github.com/nuvlaedge/nuvlaedge/tree/2.10.2) (2023-07-04)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.10.1...2.10.2)

## [2.10.1](https://github.com/nuvlaedge/nuvlaedge/tree/2.10.1) (2023-07-04)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/2.10.0...2.10.1)

**Merged pull requests:**

- 2.10.1 patch [\#87](https://github.com/nuvlaedge/nuvlaedge/pull/87) ([schaubl](https://github.com/schaubl))

## [2.10.0](https://github.com/nuvlaedge/nuvlaedge/tree/2.10.0) (2023-06-27)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/v0.3.2...2.10.0)

**Implemented enhancements:**

- extract generation of requirements files for unit tests in GH actions  [\#78](https://github.com/nuvlaedge/nuvlaedge/issues/78)
- Remove job-engine submodule [\#63](https://github.com/nuvlaedge/nuvlaedge/issues/63)
- feat: changed NuvlaEdge version parsing, using importlib package  [\#73](https://github.com/nuvlaedge/nuvlaedge/pull/73) ([ignacio-penas](https://github.com/ignacio-penas))
- feat: added common logging function \(NuvlaEdge wide\) [\#72](https://github.com/nuvlaedge/nuvlaedge/pull/72) ([ignacio-penas](https://github.com/ignacio-penas))
- feat: add support for IPRoute discovery in NuvlaEdge image [\#71](https://github.com/nuvlaedge/nuvlaedge/pull/71) ([ignacio-penas](https://github.com/ignacio-penas))
- feat: remove job-engine submodule [\#64](https://github.com/nuvlaedge/nuvlaedge/pull/64) ([ignacio-penas](https://github.com/ignacio-penas))

**Fixed bugs:**

- fix: remove 'v' prefix from tags [\#65](https://github.com/nuvlaedge/nuvlaedge/pull/65) ([ignacio-penas](https://github.com/ignacio-penas))

**Closed issues:**

- Deploy Nuvlaedge on top of k3s/submariner [\#49](https://github.com/nuvlaedge/nuvlaedge/issues/49)
- Unify release process and version updating after changes in any related part of the code [\#42](https://github.com/nuvlaedge/nuvlaedge/issues/42)
- Merge nuvlaedge images into a single installation [\#41](https://github.com/nuvlaedge/nuvlaedge/issues/41)
- Merge component repository into single one [\#40](https://github.com/nuvlaedge/nuvlaedge/issues/40)
- which k8s implementations are considered unsuitable for multi-clustering [\#39](https://github.com/nuvlaedge/nuvlaedge/issues/39)
- which k8s implementations require additional tools for multi-clustering support and what those tools are [\#38](https://github.com/nuvlaedge/nuvlaedge/issues/38)
- what k8s implementations support multi-clustering out of the box [\#37](https://github.com/nuvlaedge/nuvlaedge/issues/37)
- Investigate multi-clustering support of k8s implementations [\#36](https://github.com/nuvlaedge/nuvlaedge/issues/36)
- Compare KPIs of non-functional criteria across the k8s implementations for edge [\#35](https://github.com/nuvlaedge/nuvlaedge/issues/35)

**Merged pull requests:**

- feat\(agent\): NE\_IMAGE\_\* environment variables [\#85](https://github.com/nuvlaedge/nuvlaedge/pull/85) ([schaubl](https://github.com/schaubl))
- feat\(agent\): remove the need of having a paused job-engine-lite container [\#80](https://github.com/nuvlaedge/nuvlaedge/pull/80) ([schaubl](https://github.com/schaubl))
- extract generation of requirements files [\#79](https://github.com/nuvlaedge/nuvlaedge/pull/79) ([konstan](https://github.com/konstan))
- fix\(gpu\): refactor container and fix subcontainer image build [\#77](https://github.com/nuvlaedge/nuvlaedge/pull/77) ([schaubl](https://github.com/schaubl))
- Fix on-stop, common argument parsing and common logging [\#75](https://github.com/nuvlaedge/nuvlaedge/pull/75) ([schaubl](https://github.com/schaubl))
- feat: Dockerfile: extract package version as ARG [\#74](https://github.com/nuvlaedge/nuvlaedge/pull/74) ([schaubl](https://github.com/schaubl))
- fix: base sourcecode smells  [\#67](https://github.com/nuvlaedge/nuvlaedge/pull/67) ([ignacio-penas](https://github.com/ignacio-penas))
- docs: add basic badges to readme [\#66](https://github.com/nuvlaedge/nuvlaedge/pull/66) ([ignacio-penas](https://github.com/ignacio-penas))

## [v0.3.2](https://github.com/nuvlaedge/nuvlaedge/tree/v0.3.2) (2023-06-01)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/v0.3.1...v0.3.2)

## [v0.3.1](https://github.com/nuvlaedge/nuvlaedge/tree/v0.3.1) (2023-06-01)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/v0.3.0...v0.3.1)

## [v0.3.0](https://github.com/nuvlaedge/nuvlaedge/tree/v0.3.0) (2023-06-01)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/v0.2.0...v0.3.0)

**Implemented enhancements:**

- feat: Merge job engine [\#61](https://github.com/nuvlaedge/nuvlaedge/pull/61) ([ignacio-penas](https://github.com/ignacio-penas))
- feat: merge compute-api [\#60](https://github.com/nuvlaedge/nuvlaedge/pull/60) ([ignacio-penas](https://github.com/ignacio-penas))
- feat: Merge vpn-client [\#59](https://github.com/nuvlaedge/nuvlaedge/pull/59) ([ignacio-penas](https://github.com/ignacio-penas))

## [v0.2.0](https://github.com/nuvlaedge/nuvlaedge/tree/v0.2.0) (2023-05-30)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/v0.1.5...v0.2.0)

**Implemented enhancements:**

- feat: Add GPU scanner peripheral [\#58](https://github.com/nuvlaedge/nuvlaedge/pull/58) ([ignacio-penas](https://github.com/ignacio-penas))

**Merged pull requests:**

- docs: Update main README.md [\#57](https://github.com/nuvlaedge/nuvlaedge/pull/57) ([ignacio-penas](https://github.com/ignacio-penas))

## [v0.1.5](https://github.com/nuvlaedge/nuvlaedge/tree/v0.1.5) (2023-05-26)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/v0.1.4...v0.1.5)

## [v0.1.4](https://github.com/nuvlaedge/nuvlaedge/tree/v0.1.4) (2023-05-26)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/v0.1.3...v0.1.4)

**Implemented enhancements:**

- ci: release test 1 [\#56](https://github.com/nuvlaedge/nuvlaedge/pull/56) ([ignacio-penas](https://github.com/ignacio-penas))

## [v0.1.3](https://github.com/nuvlaedge/nuvlaedge/tree/v0.1.3) (2023-05-26)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/v0.1.2...v0.1.3)

## [v0.1.2](https://github.com/nuvlaedge/nuvlaedge/tree/v0.1.2) (2023-05-26)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/v0.1.1...v0.1.2)

## [v0.1.1](https://github.com/nuvlaedge/nuvlaedge/tree/v0.1.1) (2023-05-26)

[Full Changelog](https://github.com/nuvlaedge/nuvlaedge/compare/43891f502e3f5ae6eb4aad2689b3d19e269d0342...v0.1.1)

**Implemented enhancements:**

- Allow to define Environment Variables in the auto install context file [\#23](https://github.com/nuvlaedge/nuvlaedge/issues/23)
- ci: Add release changelog configuration [\#54](https://github.com/nuvlaedge/nuvlaedge/pull/54) ([ignacio-penas](https://github.com/ignacio-penas))
- feat: Add bluetooth peripheral bluetooth and pybluez build [\#52](https://github.com/nuvlaedge/nuvlaedge/pull/52) ([ignacio-penas](https://github.com/ignacio-penas))
- feat: Merge Agent, moved logging configuration to /etc/nuvlaedge and added … [\#51](https://github.com/nuvlaedge/nuvlaedge/pull/51) ([ignacio-penas](https://github.com/ignacio-penas))
- feat: Merge on stop [\#50](https://github.com/nuvlaedge/nuvlaedge/pull/50) ([ignacio-penas](https://github.com/ignacio-penas))
- feat: Merge peripheral manager [\#47](https://github.com/nuvlaedge/nuvlaedge/pull/47) ([ignacio-penas](https://github.com/ignacio-penas))
- feat: Merge system manager [\#46](https://github.com/nuvlaedge/nuvlaedge/pull/46) ([ignacio-penas](https://github.com/ignacio-penas))
- feat: Merge nuvlaedge common lib [\#44](https://github.com/nuvlaedge/nuvlaedge/pull/44) ([ignacio-penas](https://github.com/ignacio-penas))

**Fixed bugs:**

- fix: Merge nuvlaedge lib [\#45](https://github.com/nuvlaedge/nuvlaedge/pull/45) ([ignacio-penas](https://github.com/ignacio-penas))

**Closed issues:**

- Deploy Kubeedge cluster, deploy Nuvlaedge on-top [\#48](https://github.com/nuvlaedge/nuvlaedge/issues/48)
- Prepare release and upgrade to version 2.5.x [\#34](https://github.com/nuvlaedge/nuvlaedge/issues/34)
- Rename microservices executables to differentiate them \(instead of app.py\) [\#32](https://github.com/nuvlaedge/nuvlaedge/issues/32)
- Align Python versions \(docker base image\) of all NB Engine components [\#31](https://github.com/nuvlaedge/nuvlaedge/issues/31)
- design required workflow for supporting the watchdog [\#30](https://github.com/nuvlaedge/nuvlaedge/issues/30)
- investigate and document the procedure to install and setup ansible pull [\#29](https://github.com/nuvlaedge/nuvlaedge/issues/29)
- add test VPN server to preprod.nuvla.io [\#28](https://github.com/nuvlaedge/nuvlaedge/issues/28)
- NuvlaBox Engine 2.0 [\#27](https://github.com/nuvlaedge/nuvlaedge/issues/27)
- Update job should kill leftover installers if already finished [\#26](https://github.com/nuvlaedge/nuvlaedge/issues/26)
- Update 1.16.1 -\> 1.16.1 fails [\#25](https://github.com/nuvlaedge/nuvlaedge/issues/25)
- Prevent common issues on NuvlaBox Engine and NuvlaBox OS [\#24](https://github.com/nuvlaedge/nuvlaedge/issues/24)
- create nb-nuvla compatibility table [\#22](https://github.com/nuvlaedge/nuvlaedge/issues/22)
- update CI badges in README.md across org [\#21](https://github.com/nuvlaedge/nuvlaedge/issues/21)
- convert nuvlabox-shared-network to local scope [\#20](https://github.com/nuvlaedge/nuvlaedge/issues/20)
- adjust the --oom-score-adj to -900 or lower \(default is -8\) for the most critical NB containers [\#19](https://github.com/nuvlaedge/nuvlaedge/issues/19)
- make host\_mode peripheral managers use localhost:5080 agent api [\#18](https://github.com/nuvlaedge/nuvlaedge/issues/18)
- ignore tags on GH actions build [\#17](https://github.com/nuvlaedge/nuvlaedge/issues/17)
- improve fault tolerance for traefik [\#16](https://github.com/nuvlaedge/nuvlaedge/issues/16)
- traefik sometimes exits with exit code 0 [\#15](https://github.com/nuvlaedge/nuvlaedge/issues/15)
- create NB Engine updater container [\#14](https://github.com/nuvlaedge/nuvlaedge/issues/14)
- implement pull-mode job execution inside the NuvlaBox [\#13](https://github.com/nuvlaedge/nuvlaedge/issues/13)
- implement BLE discovery under existing bluetooth peripheral manager [\#12](https://github.com/nuvlaedge/nuvlaedge/issues/12)
- create peripheral-manager-ethernet [\#11](https://github.com/nuvlaedge/nuvlaedge/issues/11)
- create peripheral-manager-hats for rpi [\#10](https://github.com/nuvlaedge/nuvlaedge/issues/10)
- add more SixSq-specific labels to all NB Engine docker images [\#9](https://github.com/nuvlaedge/nuvlaedge/issues/9)
- refactor peripheral managers to ease community contribution [\#7](https://github.com/nuvlaedge/nuvlaedge/issues/7)
- add discovery of GPU devices [\#6](https://github.com/nuvlaedge/nuvlaedge/issues/6)
- discovery and categorization of tcp and serial peripherals [\#5](https://github.com/nuvlaedge/nuvlaedge/issues/5)
- remove "device/sensor discovery" from nuvlaedge.agent, in NB architecture image [\#4](https://github.com/nuvlaedge/nuvlaedge/issues/4)
- create peripheral manager for Modbus [\#3](https://github.com/nuvlaedge/nuvlaedge/issues/3)
- Remove mention of HOSTNAME when starting NuvlaBox-Engine [\#2](https://github.com/nuvlaedge/nuvlaedge/issues/2)
- create repository nuvlabox-lib [\#1](https://github.com/nuvlaedge/nuvlaedge/issues/1)

**Merged pull requests:**

- ci: Update bump version [\#55](https://github.com/nuvlaedge/nuvlaedge/pull/55) ([ignacio-penas](https://github.com/ignacio-penas))

# 0.1.0 (2023-05-26)


### Bug Fixes

* Fix bump-version.yml semantic bug ([1abfe39](https://github.com/nuvlaedge/nuvlaedge/commit/1abfe39e61b1e2e870cee7b881b76bf16260076a))





\* *This Changelog was automatically generated by [github_changelog_generator](https://github.com/github-changelog-generator/github-changelog-generator)*
