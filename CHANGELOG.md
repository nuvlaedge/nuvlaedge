# Changelog

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
- remove "device/sensor discovery" from agent, in NB architecture image [\#4](https://github.com/nuvlaedge/nuvlaedge/issues/4)
- create peripheral manager for Modbus [\#3](https://github.com/nuvlaedge/nuvlaedge/issues/3)
- Remove mention of HOSTNAME when starting NuvlaBox-Engine [\#2](https://github.com/nuvlaedge/nuvlaedge/issues/2)
- create repository nuvlabox-lib [\#1](https://github.com/nuvlaedge/nuvlaedge/issues/1)

**Merged pull requests:**

- ci: Update bump version [\#55](https://github.com/nuvlaedge/nuvlaedge/pull/55) ([ignacio-penas](https://github.com/ignacio-penas))

# 0.1.0 (2023-05-26)


### Bug Fixes

* Fix bump-version.yml semantic bug ([1abfe39](https://github.com/nuvlaedge/nuvlaedge/commit/1abfe39e61b1e2e870cee7b881b76bf16260076a))





\* *This Changelog was automatically generated by [github_changelog_generator](https://github.com/github-changelog-generator/github-changelog-generator)*
