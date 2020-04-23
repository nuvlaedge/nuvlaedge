#!/bin/sh

# TODO: fix name of the trigger file
trigger_file="placeholder"

log() {
  # logging wrapper
  # $1 is the custom log message

  echo "NuvlaBox USB auto-installer: ${1}"
  logger "NuvlaBox USB auto-installer: ${1}"
}



download_nuvlabox_installer() {
  # fetches the latest NuvlaBox installer script from upstream
  # $1 is the path where to store the installer

  # TODO: fix this URL
  url=https://nuvla.io/api/cloud-entry-point

  log "downloading latest NuvlaBox installer from upstream at ${url}"

  wget ${url} -O "${1}"
}


install_nuvlabox() {
  # $1 is the USB drive mountpoint where we should look for the Nuvla user credentials
  media_mountpoint="${1}"

  # once mount is populated, we need to look for the Nuvla credentials
  existing_trigger_files=$(find "${media_mountpoint}/" -name "${trigger_file}")

  # if there's no trigger file, just exit and do nothing
  [ -z "${existing_trigger_files}" ] && log "${trigger_file} not found. Do nothing" && exit 0

  # in case there is more than one trigger file
  # DEFAULTS
  found_trigger_file=${existing_trigger_files}
  trigger_file_timestamp=""
  for tf in ${existing_trigger_files}
  do
    if [ -z ${trigger_file_timestamp} ]
    then
      # first file found
      found_trigger_file="${tf}"
      continue
    fi

    trigger_file_timestamp_new=$(stat "${tf}" --printf=%Y)

    if [ ${trigger_file_timestamp_new} -gt ${trigger_file_timestamp} ]
    then
      # we choose the most recent trigger file
      found_trigger_file="${tf}"
      trigger_file_timestamp=${trigger_file_timestamp_new}
    fi
  done

  log "found ${found_trigger_file}. Auto-installing NuvlaBox..."

  nuvlabox_installer_file="/tmp/nuvlabox.installer.$(date +'%s').sh"
  download_nuvlabox_installer "${nuvlabox_installer_file}"

  log "launching the NuvlaBox installer ${nuvlabox_installer_file} ..."
  sh "${nuvlabox_installer_file}"
}


try_install_nuvlabox() {
  # $1 is the block device name
  block_device="${1}"

  # 60 seconds max to let the system auto mount the USB drive, otherwise give up
  log "waiting for USB drive mountpoint on ${block_device}"
  mountpoint=$(lsblk "${block_device}" -n -o MOUNTPOINT)

  tries=0
  while [ -z "${mountpoint}" ]
  do
    tries=$((tries+1))
    if [ $tries -gt 30 ]
    then
      (log "timeout waiting for mountpoint on ${block_device}. Nothing to do" && exit 0)
    fi
    sleep 2

    mountpoint=$(lsblk "${block_device}" -n -o MOUNTPOINT)
  done

  log "found USB drive mountpoint ${mountpoint} - checking if files are mounted and if ${trigger_file} is present"

  export mountpoint
  timeout 30 sh -c -- 'while [ -z "${files}" ]
  do
    files=$(ls "${mountpoint}")
    sleep 1
  done' ||  (log "timeout waiting for mountpoint files at ${mountpoint}. Nothing to do" && exit 0)

  install_nuvlabox "${mountpoint}"
}


pipefail=$(date +%s)

mkfifo ${pipefail}
inotifywait -m -q /dev/block/ -e CREATE > ${pipefail} &
while read path event name
do
  block_name="${path}${name}"

  device_info=$(udevadm info -q property "${block_name}")
  echo ${device_info} | grep -q -E 'DEVTYPE=partition.*SUBSYSTEM=block.*ID_BUS=usb.*ID_FS_TYPE=.*ID_FS_USAGE='

  if [ $? -eq 0 ]
  then
    # This means that this is a partition, from a block device, from a USB drive, and has a mountable filesystem
    # and in that case, it can have a mounted partition in the system
    log "found mountable USB drive ${block_name} - checking for ${trigger_file}"
    try_install_nuvlabox "${block_name}" &

  fi
done < ${pipefail}