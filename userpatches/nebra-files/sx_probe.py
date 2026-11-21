#!/usr/bin/env python3
"""Read the SX1301/SX1302 chip-version register over spidev.

Protocol note (this is what kept producing false alarms here):
the SX1301 HAL's READ_ACCESS is a *direct* 2-byte transfer, [addr, 0x00], with
the value in byte 1.  The 3-byte [0x00, addr, 0x00] form is LGW_SPI_MUX_MODE1
only -- on this Nebra carrier it returns the clock bleeding into an undriven
MISO line (0x67 at every address, which looks like a chip answer but is not).

Register facts for SX1301 (libloragw/src/loragw_reg.c, loregs[]):
  0x00 PAGE_REG -> reads 0x00
  0x01 VERSION  -> reads 0x67 (103)
A live chip therefore gives 00=00 01=67; identical values on every register
mean nothing is driving MISO.

POWER_EN is gpiochip4:3 and it must be held HIGH before any read. The reset is
that rail, not a GPIO: cycling line 3 (LOW 500 ms, HIGH, wait 2 s) is what brings
the chip out of a latched state. Asserting gpiochip4:21 (sysfs 149) or :22 (150)
was measured to do nothing on this HAT, and no header pin for reset is confirmed.
"""
import glob
import sys

try:
    import spidev
except ModuleNotFoundError:  # a fresh Armbian has no python3-spidev
    raise SystemExit(
        "spidev is not installed, so the bus cannot be opened.\n"
        "  sudo apt install -y python3-spidev\n"
        "  or install the full dependency set:\n"
        "    build-essential gpiod python3-libgpiod python3-spidev\n"
        "If you are inside a venv/conda/pyenv shell, leave it: those do not see\n"
        "apt-installed modules. 'command -v python3' must be /usr/bin/python3."
    )

BUSES = [a for a in sys.argv[1:] if not a.startswith("-")] or sorted(glob.glob("/dev/spidev*"))
SPEED = 2_000_000          # Nebra units had their SPI NOR flash removed: 8 MHz corrupts
REGS = (0x00, 0x01, 0x02, 0x03)


def read_reg(spi, reg: int) -> int:
    """Direct (non-mux) SX1301 read: the value comes back in byte 1."""
    return spi.xfer2([reg, 0x00])[1]


def probe(path: str) -> bool:
    spi = spidev.SpiDev()
    try:
        bus, cs = path.rsplit("/dev/spidev", 1)[1].split(".")
        spi.open(int(bus), int(cs))
        spi.max_speed_hz = SPEED
        spi.mode = 0
        regs = {r: read_reg(spi, r) for r in REGS}
    finally:
        spi.close()

    print(f"{path}: " + " ".join(f"{r:02x}={v:02x}" for r, v in regs.items()))

    if regs[0x01] == 0x67 and regs[0x00] == 0x00:
        print(f"{path}: SX1301 ALIVE (VERSION=0x67 at reg 0x01)")
        return True
    if regs[0x00] == 0x10:
        print(f"{path}: SX1302 detected (0x10)")
        return True
    if len(set(regs.values())) == 1:
        print(f"{path}: FLOATING MISO - every register reads 0x{regs[0x01]:02x}; "
              "card unseated, unpowered (POWER_EN low) or held in reset")
    else:
        print(f"{path}: no SX1301 answer {regs} - check POWER_EN / reseat the card")
    return False


def main() -> int:
    if not BUSES:
        print("no /dev/spidev* present - SPI overlay not applied")
        return 1
    ok = False
    for b in BUSES:
        try:
            ok = probe(b) or ok
        except Exception as exc:  # noqa: BLE001 - surface the real errno text
            print(f"{b}: ERROR {exc}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
