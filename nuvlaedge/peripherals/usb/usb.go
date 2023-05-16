package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"os/exec"
	"runtime/debug"
	"strings"
	"time"

	"github.com/google/gousb"
	"github.com/google/gousb/usbid"
	log "github.com/sirupsen/logrus"
)

const DatetimeFormat = "01022006150405"
const NuvlaEdgeRootFileSystem = "/srv/nuvlaedge/shared/"
const PeripheralsFolder = ".peripherals/"
const PeripheralName = "usb"
const ChannelPath = NuvlaEdgeRootFileSystem + PeripheralsFolder + PeripheralName + "/buffer/"

var lsUsbFunctional = false

func getSerialNumberForDevice(devicePath string) string {
	cmd := exec.Command("udevadm", "info", "--attribute-walk", devicePath)

	stdout, cmdErr := cmd.Output()
	var serialNumber string = ""
	var backupSerialNumber string = ""

	if cmdErr != nil {
		log.Errorf("Unable to run udevadm for device %s. Reason: %s", devicePath, cmdErr.Error())
		return serialNumber
	}

	for _, line := range strings.Split(string(stdout), "\n") {
		if strings.Contains(line, "serial") {
			if strings.Contains(line, ".usb") {
				backupSerialNumber = strings.Split(line, "\"")[1]
				continue
			}
			serialNumber = strings.Split(line, "\"")[1]
			break
		}
	}

	if len(serialNumber) == 0 && len(backupSerialNumber) > 0 {
		serialNumber = backupSerialNumber
	}

	return serialNumber
}

func onContextError() {
	if !lsUsbFunctional {
		log.Warn("Unable to initialize USB discovery. Host might be incompatible with this " +
			"peripheral manager. Trying again later...")
		time.Sleep(10 * time.Second)
		log.Info(string(debug.Stack()))
		os.Exit(0)
	}
}

func getUsbContext() *gousb.Context {
	defer onContextError()
	c := gousb.NewContext()
	lsUsbFunctional = true
	return c
}

func formatFileName() string {
	now := time.Now().Format(DatetimeFormat)
	return string(now) + "_" + PeripheralName + ".json"
}

func checkFileSystem() {
	log.Infof("Creating USB folder structure %s", ChannelPath)
	if err := os.MkdirAll(ChannelPath, os.ModePerm); err != nil {
		log.Fatal(err)
	}
}

func saveDiscoveredPeripherals(data map[string]interface{}) {
	bData, _ := json.Marshal(data)
	file := ChannelPath + formatFileName()
	log.Infof("Saving USB peripherals to %s", file)
	_ = os.WriteFile(
		file,
		bData,
		0644)
}

func main() {
	log.Info("Peripheral Manager USB has started")

	// Only one context should be needed for an application.  It should always be closed.
	ctx := getUsbContext()
	defer func(ctx *gousb.Context) {
		err := ctx.Close()
		if err != nil {

		}
	}(ctx)

	var available string = "True"
	var devInterface string = "USB"
	var videoFilesBasedir string = "/dev/"
	checkFileSystem()

	for true {
		// Default name for USB
		name := "UNNAMED USB Device"
		var message = map[string]interface{}{}

		_, devErr := ctx.OpenDevices(func(desc *gousb.DeviceDesc) bool {
			identifier := fmt.Sprintf("%s:%s", desc.Vendor, desc.Product)

			devicePath := fmt.Sprintf("/dev/bus/usb/%03d/%03d", desc.Bus, desc.Address)

			vendor := usbid.Vendors[desc.Vendor]

			product := vendor.Product[desc.Product]

			description := fmt.Sprintf("%s device [%s] with ID %s. Protocol: %s",
				devInterface,
				product,
				identifier,
				usbid.Classify(desc))

			if product != nil {
				name = fmt.Sprintf("%s", product)
			} else {
				name = fmt.Sprintf("%s with ID %s", name, identifier)
			}

			classesAux := make(map[string]bool)

			classes := make([]interface{}, 0)

			for _, cfg := range desc.Configs {
				for _, intf := range cfg.Interfaces {
					for _, ifSetting := range intf.AltSettings {
						class := fmt.Sprintf("%s", usbid.Classes[ifSetting.Class])
						if _, exists := classesAux[class]; !exists {
							classesAux[class] = true
							classes = append(classes, class)
						}
					}
				}
			}

			serialNumber := getSerialNumberForDevice(devicePath)

			peripheral := map[string]interface{}{
				"name":        name,
				"description": description,
				"interface":   devInterface,
				"identifier":  identifier,
				"classes":     classes,
				"available":   available,
				//"resources": n/a
				// Leaving out the resources attribute since this is only used for
				// block devices, which at the moment are already monitored by the
				// NB Agent, so no need to duplicate the same information.
				// To re-implement this attribute, check the raw legacy code in [1]
			}

			if len(vendor.Name) > 0 {
				peripheral["vendor"] = vendor.Name
			}

			if product != nil {
				peripheral["product"] = fmt.Sprintf("%s", product)
			}

			if len(devicePath) > 0 {
				peripheral["device-path"] = devicePath
			}

			if len(serialNumber) > 0 {
				peripheral["serial-number"] = serialNumber
			}

			devFiles, vfErr := ioutil.ReadDir(videoFilesBasedir)
			if vfErr != nil {
				log.Errorf("Unable to read files under %s. Reason: %s", videoFilesBasedir, vfErr.Error())
				return false
			}

			for _, df := range devFiles {
				if strings.HasPrefix(df.Name(), "video") {
					vfSerialNumber := getSerialNumberForDevice(videoFilesBasedir + df.Name())
					if vfSerialNumber == serialNumber {
						peripheral["video-device"] = videoFilesBasedir + df.Name()
						break
					}
				}
			}

			// we now have a peripheral categorized, but is it new
			message[identifier] = peripheral
			return false
		})
		jsonMessage, _ := json.MarshalIndent(message, "", "  ")
		log.Infof("Usb found with feats: %s", string(jsonMessage))
		log.Infof("Generating File name: %s", formatFileName())
		saveDiscoveredPeripherals(message)

		if devErr != nil {
			log.Errorf("A problem occurred while listing the USB peripherals %s. Continuing...", devErr)
		}

		time.Sleep(30 * time.Second)
	}
}