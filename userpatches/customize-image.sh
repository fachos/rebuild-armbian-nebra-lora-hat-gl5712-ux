#!/usr/bin/env bash
# Armbian customize-image.sh — runs inside the image chroot as root.
# Called by the build framework as: customize-image.sh <RELEASE>
#
# Payload files live next to this script in userpatches/nebra-files/.
# Everything here is idempotent: a rebuild must not corrupt the image.

main() {
	local release="${1:-trixie}"
	local here
	here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
	local payload="$here/nebra-files"

	display_alert "Nebra HAT customisation" "release ${release}" "info"

	# ------------------------------------------------------------ SPI overlay
	# The stock rk3399-spi-spidev overlay is enough for this HAT: no custom dtbo,
	# no device-tree patch. Just make sure bus 1 is exposed at the speed the
	# board tolerates.
	local envfile=/boot/armbianEnv.txt
	if [[ -f $envfile ]]; then
		grep -q '^overlays=.*rk3399-spi-spidev' "$envfile" ||
			sed -i 's/^\(overlays=\)/\1rk3399-spi-spidev /' "$envfile"
		grep -q '^overlays=' "$envfile" ||
			echo 'overlays=rk3399-spi-spidev' >> "$envfile"
		grep -q '^param_spidev_spi_bus=' "$envfile" ||
			echo 'param_spidev_spi_bus=1' >> "$envfile"
		grep -q '^param_spidev_max_freq=' "$envfile" ||
			echo 'param_spidev_max_freq=2000000' >> "$envfile"
		# u-boot takes the last overlays= line; collapse duplicates
		awk '!(/^overlays=/ && seen++)' "$envfile" > "$envfile.tmp" && mv "$envfile.tmp" "$envfile"
	fi

	# ---------------------------------------------------------------- packages
	# One unknown name aborts the whole apt transaction, so only names that
	# exist in the target release go here. Debian 13: libgpiod 2.x = gpiod +
	# python3-libgpiod (there is no 'libgpiod2'), and spidev is its own package.
	apt-get update -qq
	DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
		gpiod python3-libgpiod python3-spidev python3 git curl build-essential >/dev/null
	# fail the build here rather than on the user's first probe
	python3 -c 'import spidev; from gpiod.line import Direction, Value' || {
		echo "customize-image: python packages did not land (spidev / gpiod.line)" >&2
		exit 1
	}

	# ------------------------------------------------------- hardware payload
	# Baked in so the board can be diagnosed with no network access.
	install -d /usr/local/share/nebra
	install -m 0755 "$payload/nebra_hat.py" /usr/local/sbin/nebra-hat
	install -m 0644 "$payload/sx_probe.py"  /usr/local/share/nebra/sx_probe.py
	install -m 0644 "$payload/nebra-lora-power.service" /etc/systemd/system/
	systemctl enable nebra-lora-power.service >/dev/null 2>&1 || true

	display_alert "Nebra HAT customisation done" "spi1 @ 2 MHz · power service enabled" "info"
}

main "$@"
