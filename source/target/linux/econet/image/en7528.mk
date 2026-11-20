TRX_ENDIAN := le

define Device/en7528_generic
  DEVICE_VENDOR := EN7528
  DEVICE_MODEL := Generic
  DEVICE_DTS := en7528_generic
endef
TARGET_DEVICES += en7528_generic

define Device/dasan_h660gm-a
  DEVICE_VENDOR := DASAN
  DEVICE_MODEL := H660GM-A
  DEVICE_PACKAGES := kmod-usb2 kmod-mt7603 kmod-mt7615e kmod-mt7663-firmware-ap
  TRX_MODEL := Dewberry
  IMAGES := tclinux.trx
  IMAGE/tclinux.trx := append-kernel | lzma | tclinux-trx
endef

define Device/dasan_h660gm-a-airtel
  $(Device/dasan_h660gm-a)
  DEVICE_VARIANT := Airtel
  DEVICE_DTS := en7528_dasan_h660gm-a-airtel
endef
TARGET_DEVICES += dasan_h660gm-a-airtel

define Device/dasan_h660gm-a-generic
  $(Device/dasan_h660gm-a)
  DEVICE_VARIANT := Generic
  DEVICE_DTS := en7528_dasan_h660gm-a-generic
endef
TARGET_DEVICES += dasan_h660gm-a-generic

# JioFiber JCOW407 (Reliance Jio GPON ONT): EN7528 + MT7663, 512MB DDR3,
# 256MB SPI-NAND. Same SoC/wifi/image format as the DASAN H660GM-A.
define Device/jio_jcow407
  DEVICE_VENDOR := JioFiber
  DEVICE_MODEL := JCOW407
  DEVICE_DTS := en7528_jio_jcow407
  # luci-ssl + px5g pull in the TLS stack so the LuCI web UI is reachable over
  # https://192.168.1.1 (uhttpd generates a self-signed cert on first boot);
  # without it only http works and HTTPS-first browsers fail to connect.
  DEVICE_PACKAGES := kmod-usb2 kmod-mt7603 kmod-mt7615e kmod-mt7663-firmware-ap \
	luci-ssl px5g-mbedtls
  TRX_MODEL := Dewberry
  IMAGES := tclinux.trx
  IMAGE/tclinux.trx := append-kernel | lzma | tclinux-trx
endef
TARGET_DEVICES += jio_jcow407

# Titanium-2122A (Excitel) — EN7528, 256MB SPI-NAND, 256MB RAM,
# MT7603 (2.4G) + MT7663 (5G), same MAC-at-0x3fe48 as DASAN/JCOW407.
define Device/titanium_2122a
  DEVICE_VENDOR := Titanium
  DEVICE_MODEL := 2122A
  DEVICE_DTS := en7528_titanium_2122a
  DEVICE_PACKAGES := kmod-usb2 kmod-mt7603 kmod-mt7615e kmod-mt7663-firmware-ap \
	luci-ssl px5g-mbedtls luci-app-econet-xpon
  TRX_MODEL := Dewberry
  IMAGES := tclinux.trx
  # This bldr is a "free bootbase" build: it decompresses the kernel at
  # 0x80002000, while OpenWrt links it at 0x80020000. Prepend the jr-a0
  # stub + 0x1E000 pad so the kernel still lands at its link address.
  IMAGE/tclinux.trx := append-kernel | tclinux-free-bootbase-jump | lzma | tclinux-trx
endef
TARGET_DEVICES += titanium_2122a

# Same board, but booting the tclinux_slave bank: the squashfs sits at
# 0x1980000 + 0x400000 = 0x1d80000 instead of 0x480000.
define Device/titanium_2122a_slave
  $(Device/titanium_2122a)
  DEVICE_VARIANT := Slave bank
  DEVICE_DTS := en7528_titanium_2122a_slave
endef
TARGET_DEVICES += titanium_2122a_slave
