#!/usr/bin/env bash

IMAGE_URL='https://downloads.raspberrypi.org/raspbian_lite/images/raspbian_lite-2019-06-24/2019-06-20-raspbian-buster-lite.zip'
LOCAL_RASPBIAN_IMAGE='/tmp/raspbian.img'

download_image () {
  wget $1 -O /tmp/raspbian.zip
  unzip -p /tmp/raspbian.zip > $LOCAL_RASPBIAN_IMAGE
}

apt-get update
apt-get install -y binfmt-support	bundler	git golang jq qemu qemu-user-static ruby unzip zip

download_image $IMAGE_URL

MOUNT_DIR=/mnt
MOUNT_BOOT_DIR=/mnt/boot

IMAGE_PATH=`eval ls $LOCAL_RASPBIAN_IMAGE`

##
### Prepare the mount directory
##
mkdir -p $MOUNT_BOOT_DIR
# Get sector size of the disk image
SECTOR_SIZE=`fdisk -l $IMAGE_PATH | grep Units | awk -F"[= ]" '{print $6}'`
# Get the start of the Linux and Boot partitions
LINUX_START=`fdisk -l $IMAGE_PATH | grep Linux | awk -F" " '{print $2}'`
BOOT_START=`fdisk -l $IMAGE_PATH |grep FAT32 | awk -F" " '{print $2}'`
# Calculate the real Linux and Boot partitions start offset
let offset=SECTOR_SIZE*LINUX_START
let boot_offset=SECTOR_SIZE*BOOT_START
# Mount Raspbian
mount -v -o offset=$offset -o rw -t ext4 $IMAGE_PATH $MOUNT_DIR
mount -v -o offset=$boot_offset -o rw -t vfat $IMAGE_PATH $MOUNT_BOOT_DIR
# bind mount
mount --bind /dev $MOUNT_DIR/dev/
mount --bind /sys $MOUNT_DIR/sys/
mount --bind /proc $MOUNT_DIR/proc/
mount --bind /dev/pts $MOUNT_DIR/dev/pts
# patch
sed -i 's/^/#/g' $MOUNT_DIR/etc/ld.so.preload
# prepare for chroot
cp /usr/bin/qemu-arm-static $MOUNT_DIR/usr/bin/


touch $MOUNT_BOOT_DIR/ssh

chroot $MOUNT_DIR apt update -y

curl -fsSL https://get.docker.com -o get-docker.sh
sed -i 's/9)/10)/' get-docker.sh

mv get-docker.sh $MOUNT_DIR/tmp
chroot $MOUNT_DIR sh /tmp/get-docker.sh

chroot $MOUNT_DIR apt install -y openvpn docker-compose

chroot $MOUNT_DIR usermod -aG docker $USER
chroot $MOUNT_DIR usermod -aG docker pi

wget https://github.com/nuvlabox/deployment/archive/1.0.0.zip
unzip 1.0.0.zip
cp deployment-1.0.0/docker-compose.yml $MOUNT_DIR/home/pi/

sed -i 's/^#//g' $MOUNT_DIR/etc/ld.so.preload

umount -l $MOUNT_DIR/{dev/pts,dev,sys,proc,boot,}
