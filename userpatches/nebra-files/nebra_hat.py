#!/usr/bin/env python3
"""Hold the Nebra HAT's power enable, reset the concentrator, drive the status LED.

    gpiochip4 line 3   GPIO4_A3  POWER_EN (TCXO / PA rail) -> held HIGH
    gpiochip4 line 28  GPIO4_D4  status LED                -> HIGH = lit

This file knows nothing about any gateway application: it powers the HAT, resets
the chip the one way that works, and leaves the SPI bus free for whatever runs
next — `sx_probe.py`, `test_loragw_reg`, or your own code.

RESET is the POWER_EN rail, not a GPIO. Asserting the lines that sources name as
NRESET (`gpiochip4` line 21 / sysfs 149 and line 22 / sysfs 150) during power-up
was measured to do nothing on this HAT: the chip answered `0x67` every time, both
before and after release. So this service performs the reset the only way that
works — drop the rail, raise it, let the TCXO settle:

    POWER_EN LOW 500 ms -> POWER_EN HIGH -> sleep 2 s -> probe

Why a long-running service instead of `gpioset`: `gpioset` exits immediately and
releases the line, the TCXO rail drops, and the concentrator dies mid-init. This
process holds the lines for its lifetime and releases them cleanly on stop.

`systemctl restart nebra-lora-power` re-runs the cycle, which recovers a latched
chip without pulling power.
"""
import subprocess
import time

try:
    import gpiod
    from gpiod.line import Direction, Value
except ModuleNotFoundError:
    raise SystemExit(
        "libgpiod 2.x python bindings missing (this script needs gpiod.line).\n"
        "  sudo apt install -y python3-libgpiod gpiod        # Debian 13 / Armbian trixie\n"
        "  or install the full dependency set:\n"
        "    build-essential gpiod python3-libgpiod python3-spidev\n"
        "Do not install libgpiod 1.x bindings for this: only the 2.x module exposes\n"
        "gpiod.line.Direction / Value, which is what request_lines() below uses."
    )

CHIP = "/dev/gpiochip4"
POWER_LINE = 3
LED_LINE = 28
LED_ACTIVE_HIGH = True          # flip if the LED is inverted on your board rev
POWER_DOWN_SECONDS = 0.5        # the reset pulse — on the rail, not a GPIO
POWER_SETTLE_SECONDS = 2.0      # TCXO + MCU startup before the first SPI access
PROBE = "/usr/local/share/nebra/sx_probe.py"
LOG = "/var/log/nebra-hat.log"


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} nebra-hat: {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def probe() -> None:
    """Report once, at start, whether the concentrator answers."""
    try:
        out = subprocess.run(["/usr/bin/python3", PROBE], capture_output=True,
                             text=True, timeout=25)
        for line in (out.stdout or out.stderr or "").strip().splitlines():
            log("probe: " + line)
    except Exception as exc:                      # noqa: BLE001
        log(f"probe skipped: {exc}")


def main() -> None:
    req = gpiod.request_lines(
        CHIP,
        consumer="nebra-hat",
        config={
            # start with the rail DOWN, then raise it: that is the reset
            POWER_LINE: gpiod.LineSettings(direction=Direction.OUTPUT,
                                           output_value=Value.INACTIVE),
            LED_LINE: gpiod.LineSettings(
                direction=Direction.OUTPUT,
                output_value=Value.ACTIVE if LED_ACTIVE_HIGH else Value.INACTIVE,
            ),
        },
    )
    try:
        log(f"reset: POWER_EN line {POWER_LINE} LOW {POWER_DOWN_SECONDS}s")
        time.sleep(POWER_DOWN_SECONDS)
        req.set_value(POWER_LINE, Value.ACTIVE)
        log(f"reset: POWER_EN HIGH, settling {POWER_SETTLE_SECONDS}s, LED line {LED_LINE} on")
        time.sleep(POWER_SETTLE_SECONDS)
        probe()
        while True:                  # keep both lines claimed for the life of the unit
            time.sleep(60)
    finally:
        req.release()
        log("released POWER_EN — concentrator is now unpowered")


if __name__ == "__main__":
    main()
