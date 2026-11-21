# Getting Armbian Rock Pi 4B+ with Nebra LoRa HAT

A small Armbian `userpatches` set that builds a **Rockpi 4B+ image where the Nebra
LoRa HAT already works**: SPI bus exposed at the right speed, power enable held
from boot, status LED wired, and the field diagnostics installed.

Board: `rockpi-4bplus` · RK3399 · 2 GB · Debian minimal · kernel `current` (6.18.x)

The bring-up procedure itself — 40-pin map, reset sequence, SPI quirks, what makes
this module different — is documented step by step in
[armbian-nebra-lora-hat-gl5712-ux](https://github.com/fachos/armbian-nebra-lora-hat-gl5712-ux);
this repo only automates it into an image.

## Why userpatches, not a fork of armbian/build

The instinct with custom kernels is to fork `armbian/build`. **For this HAT there
is no kernel change to make.** The concentrator is driven from userspace over
`spidev` and GPIO, so a fork would mean:

- a ~2 GB clone to keep in sync
- merge conflicts on every Armbian release
- a kernel patch carried forever, for nothing

Armbian's supported extension point is `userpatches/`:

| File | Role |
|---|---|
| `userpatches/config-nebra.conf` | board, branch, release, build options |
| `userpatches/customize-image.sh` | runs in the chroot: SPI overlay, packages, services |
| `userpatches/nebra-files/` | the payload baked into the image |

Fork only if you change kernel code or need a new device-tree node compiled in.

## Build

```bash
git clone --depth 1 https://github.com/armbian/build.git
cd build

git clone https://github.com/fachos/rebuild-armbian-nebra-lora-hat-gl5712-ux.git /tmp/nebra
cp -a /tmp/nebra/userpatches/. userpatches/

./compile.sh nebra
```

`./compile.sh nebra` picks up `config-nebra.conf` directly. First run downloads
the toolchain and kernel sources: about 40–90 minutes on 8 cores.

Output: `output/images/*.img`, plus `.sha` and `.xz` per `COMPRESS_OUTPUTIMAGE`.

> **Timestamps.** Armbian stamps images with the build date, so two builds on
> different days are not byte-identical even with identical inputs. That is
> expected. After editing `customize-image.sh`, pass `ARTIFACT_IGNORE_CACHE=yes`
> or the cached rootfs is reused and your change never lands.

## What the image contains

- `/boot/armbianEnv.txt`: `overlays=rk3399-spi-spidev`,
  `param_spidev_spi_bus=1`, `param_spidev_max_freq=2000000` (idempotent)
- `nebra-lora-power.service` enabled: holds POWER_EN and lights the status LED
- `nebra-hat` in `/usr/local/sbin`, and `sx_probe.py` in `/usr/local/share/nebra`
  so a failure can be diagnosed with no network
- `gpiod`, `python3-libgpiod`, `python3-spidev`, `build-essential`, `git`, `curl`
  — the build aborts if `import spidev` / `gpiod.line` does not work in the image

## Options

`config-nebra.conf`, and nothing else:

```bash
BOARD=rockpi-4bplus
BRANCH=current
RELEASE=trixie
BUILD_MINIMAL=no
BUILD_DESKTOP=no
KERNEL_CONFIGURE=no
EXPERT=yes
COMPRESS_OUTPUTIMAGE=sha,img,xz
CLEAN_LEVEL="make-atf,make-uboot"
```

No hostname override, no SSH key seeding, no vendor identity: the image is a
stock Armbian install with the HAT layer added. You log in with the normal
Armbian credentials on first boot.

There is also **no serial key, licence key or onboarding key** anywhere in this
path. Nebra's miner stack used a per-device identity held in the HAT's secure
element for fleet onboarding; this build never reads it, never writes it, and does
not need it. The concentrator is driven directly over SPI and GPIO, so the board
works with no vendor identity at all.

## Verify after first boot

```bash
ls -l /dev/spidev1.0                  # exists
systemctl is-active nebra-lora-power  # active
sudo python3 /usr/local/share/nebra/sx_probe.py
# expect: SX1301 ALIVE (VERSION=0x67 at reg 0x01)
```

`sx-probe` reporting `0x66` everywhere means the chip is in reset or unpowered —
not a broken image. The bring-up notes explain why, and what to check first.

## OS image (if you would rather not build)

Use the **Debian minimal** Armbian build for this board — 2 GB of RAM is not a
place for a desktop image:

<https://armbian.com/boards/rockpi-4bplus>

Prefer to do it by hand? Every step in that image is written out as a manual
procedure — pin map, reset timing, SPI settings, calibration — in
[armbian-nebra-lora-hat-gl5712-ux](https://github.com/fachos/armbian-nebra-lora-hat-gl5712-ux).
Four commands and about twenty minutes. The image build exists for
reproducibility, not because the manual path is hard.

## Support

If this saved you time, you can put a little back — it goes into bench hardware
and more notes like these.

- **Ko-fi** — <https://ko-fi.com/fachos>
- **BTC** — `3GXWxonjriTtboDWDvTTBv3VJ1nhvv3fMW`
- **SOL** — `HbDMoGWS1Kj23qSfon9XK2F9rzbdFmh7nwsnB5j8TXup`
- **POL** — `0xe09c73Ad7a4eA66Cc8452809CAE62ded287f830e`

Crypto transfers are irreversible — verify every character before sending.


## Licence

MIT — see [LICENSE](LICENSE).
