# Thunderobot K78 RGB Control

[Türkçe](README.md) · **English**

Open-source RGB control for the Thunderobot K78 keyboard (wired, SinoWealth SH68F90, USB `258A:0049`).
Live per-key RGB effects with no vendor software and **no flash writes**.

## Features

- **22 effects:** rainbow wave, rainbow wheel, neon stream, sine wave, scanner, windmill, storm, waterfall,
  raindrops, stars, blossoming, snake… plus keypress effects: reaction, flash away, ripples, shadow, collision.
  Each one can run in rainbow colours or a single colour.
- **Key painting:** click or drag over the on-screen keyboard to colour keys; painted keys stay on top of the effect.
- **Layers:** keypress glow, CPU load meter (on the 1…0 row), Caps/Num Lock indicator.
- **Profiles**, system tray mode, start with Windows, and a choice of what the keyboard shows when the app quits.
- **Command-line tool** (`k78ctl.py`): colour/key/pixel commands, protocol reads, guarded persistent profile writes.

## Requirements

- Windows 10/11
- Python 3.10+ (standard library only; tkinter included)
- Thunderobot K78, VID/PID `258A:0049`. Other keyboards reuse this VID/PID — see the warning below.

## Usage

```powershell
python k78gui.py            # GUI
python k78gui.py --tray     # start hidden in the tray

python k78ctl.py list       # list HID collections (sends nothing)
python k78ctl.py fill ff0000
python k78ctl.py key --bg 000000 W ffffff A ffffff S ffffff D ffffff
python k78ctl.py wave --seconds 10
python k78ctl.py map        # key -> LED map
python k78engine.py --base ripples   # headless effect engine
```

When the app quits, the keyboard keeps the last frame (or whatever you chose in Settings). To get the keyboard's
own built-in effects back, press **Fn** to pick an effect or unplug and replug it. The firmware has no USB
command for returning to them.

## ⚠️ Safety

- **Live effects are safe:** report 8 only writes the colour buffer in the keyboard's RAM; flash is never touched.
- **`k78ctl.py persist` writes to flash.** By default it only shows a preview; an actual write needs
  `--base flash|ram --write --confirm YAZ`. The command and address are fixed in the code (profile sector `0xB600` only).
- The **ISP command (`05 75`) is blocked** in the code, and there is no free-form flash write through report 6.
- **Do not use this on other keyboards.** `258A:0049` is a shared ID from the SinoWealth reference design.
  OpenRGB disabled its driver for this ID after it bricked Redragon keyboards that use the same ID.
  This tool was written against the K78's firmware.
- Take a full firmware backup before changing anything (e.g. with [sinowisp](https://github.com/karstx/sinowisp)).
- The software is provided "as is"; you are responsible for your hardware.

## Files

| File | Purpose |
|---|---|
| `k78ctl.py` | HID layer (Windows `hid.dll` via ctypes), protocol, CLI, LED map |
| `k78engine.py` | 30 fps effect engine (layers, key polling, CPU meter) |
| `k78effects.py` | Effect library |
| `k78layout.py` | Physical key layout |
| `k78gui.py` | tkinter GUI |
| `k78tray.py` | Dependency-free system tray icon |
| `ghidra/scripts/` | Ghidra scripts for firmware analysis (the firmware itself is not included) |
| `docs/PROTOCOL.md` | Reverse-engineered HID protocol (in Turkish) |

## Credits

- [OpenRGB](https://gitlab.com/CalcProgrammer1/OpenRGB) — first documentation of the SinoWealth keyboard protocol
- [sinowisp / sinowealth-kb-tool](https://github.com/karstx/sinowisp) and [SMK](https://github.com/karstx/smk) — SinoWealth ISP and platform details
- [Ghidra](https://github.com/NationalSecurityAgency/ghidra)

Not affiliated with Thunderobot. Thunderobot is a trademark of its owner.

## License

[MIT](LICENSE)
