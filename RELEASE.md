# Release new base image for NuvlaBox

> *Note:* this is work in progress towards the NuvlaBox OS

## Create base image for Raspberry Pi

To create a base image to burn new SD Cards for NuvlaBox on the Raspberry Pi, run this [script](image-create.sh) on a Ubuntu 18.04, as super:

```
sudo su -
bash image-create.sh
```

The resulting `/tmp/raspbian.img` image will contain the image to release and which can be used with tools such as Etcher to bake new SD Cards.

From there, the standard [NuvlaBox Engine](https://docs.nuvla.io/docs/dave/nuvlabox/nuvlabox-engine.html) instructions can be followed to complete the installation and configuration of a NuvlaBox on a Raspberry Pi.
