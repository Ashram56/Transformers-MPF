# System requirements

What a computer needs to run this workspace: MPF (the game), Godot with the GMC add-on (the DMD and sound),
optionally MPF Monitor (the virtual playfield), TerryRed's PuP Pack (videos on extra screens) and Visual Pinball
X (Windows). Every version below is what `scripts/setup.py` installs; they are pinned in `scripts/toolchain.py`.

The quickest route is the installer for your OS (the one lines are in the [README](../README.md#install)). It
installs only what is missing and then runs `scripts/setup.py`. From a clone:

| OS | Command (in the repository) |
|---|---|
| Windows 10/11 | `powershell -ExecutionPolicy Bypass -File scripts\install\install_prereqs_windows.ps1` |
| macOS 12+ | `scripts/install/install_prereqs_macos.sh` |
| Linux | `scripts/install/install_prereqs_linux.sh` |

Each installer takes `--dry-run` (`-DryRun` on Windows), which prints the plan and changes nothing. On Windows,
`-Vpx` (and `-Table <your .vpx>`) also sets up Visual Pinball X ([vpx.md](vpx.md)). `--proc` (`-Proc`) installs
the P-ROC's driver only: the game has no P-ROC run yet ([hardware.md](hardware.md)). Arguments after `--` go to
`setup.py` (Windows: any argument the script does not know), for example `-- --skip-media`.

## Summary

| | Windows | macOS | Linux |
|---|---|---|---|
| OS version | Windows 10 (1809+) or 11, 64-bit | macOS 12 Monterey or newer | glibc 2.28+ (Ubuntu 20.04+, Debian 11+, Fedora 36+, any current Arch) |
| CPU | x86_64, or ARM64 | Intel or Apple silicon | x86_64 or arm64 (aarch64) |
| Python | **3.11** (3.10 to 3.14 work) | **3.11** | **3.11** |
| Git | 2.x | 2.x (Xcode Command Line Tools or Homebrew) | 2.x |
| Graphics | Vulkan 1.0 or OpenGL 3.3 | Metal (directly, or through MoltenVK) | Vulkan 1.0 or OpenGL 3.3 (Mesa's software renderer works too) |
| Sound | any (WASAPI) | any (CoreAudio) | PulseAudio or PipeWire, else ALSA |
| Disk | 2 GB free, plus the PuP Pack's videos when it is on | same | same |
| RAM | 4 GB | 4 GB | 4 GB |
| Network | for the first setup only | same | same |
| Visual Pinball X | 10.7 or later (optional, [vpx.md](vpx.md)) | no | no |

## Python

**Use Python 3.11**, the version the installers install and CI tests. MPF 0.80.1 accepts 3.10 to 3.14;
`setup.py` refuses anything older than 3.10. `ruamel.yaml.clib` is pinned to 0.2.14 before Python 3.13
(`scripts/toolchain.py` says why).

| OS | Where Python 3.11 comes from |
|---|---|
| Windows | `winget install Python.Python.3.11` (current user), else the python.org 3.11.9 installer. Found through the `py` launcher, never the Microsoft Store's `python` stub. |
| macOS | `brew install python@3.11` with Homebrew, else the python.org 3.11.9 universal2 `.pkg` (asks for an admin password). |
| Debian 12 | the distribution's `python3.11`, `python3.11-venv`, `python3.11-dev` |
| Ubuntu 22.04 / 24.04 | the deadsnakes PPA |
| Fedora / RHEL 9 | `dnf install python3.11 python3.11-devel` |
| Arch, Debian 13, anything else | a standalone CPython 3.11 installed with [uv](https://docs.astral.sh/uv/) (no compiler, nothing system-wide) |

On Windows the installer also turns on long path support (administrator rights once) and sets
`git config --global core.longpaths true`. On Linux, `--python-any` accepts any 3.10 to 3.14 already installed.

## The repository and the PuP Pack submodule

Everything the game needs is in this one repository: the ROM extraction's package is in `rom/` (no ROM: it is
never committed). The only submodule is `pup_pack`, the owner's private copy of TerryRed's PuP Pack
(Ashram56/Transformers-PuP). Without access to it the game installs and plays without the PuP; with
`TF_PUP_ZIP=<the zip TerryRed publishes>` setup installs the pack from the author's zip instead
([pup.md](pup.md)); `TF_PUP=0` leaves it out. The installers ask for a GitHub token only when they need one.

## Godot 4.6.3 (GMC 1.0.0)

`setup.py` downloads the official Godot 4.6.3 build for the OS and CPU into `tools/godot/` (4.6 or newer for the
PuP's video add-on). GMC 1.0.0 goes into `game/addons/mpf-gmc/`.

- **Windows:** any GPU driver with Vulkan 1.0 or OpenGL 3.3. The PuP's videos play through GoZen (FFmpeg) with
  Direct3D 11 Video / DXVA2 decoding on the GPU, nothing to install.
- **macOS:** the universal build runs natively on Intel and Apple silicon. The PuP's videos play through the
  `native_video` add-on (AVFoundation).
- **Linux:** Godot loads the X11/Wayland, GL/Vulkan, font, sound and udev libraries the Linux installer installs.
  The PuP's videos play through GoZen.
- **Without a screen** (a server, CI): Xvfb. `run.py` and the render check then start Godot under `xvfb-run`.
  The installer adds Xvfb when `DISPLAY` is not set, or with `--xvfb`.

## MPF Monitor (installed by default; `--no-monitor` leaves it out)

`mpf-monitor` 1.0.0, a PyQt6 application (about 250 MB of Qt wheels). On Linux it needs the X11/xcb libraries the
installer adds. Its PyPI release lacks four Qt Designer files; `setup.py` copies them from the release's git tag.

## Visual Pinball X (Windows, optional)

`-Vpx` installs `olefile` and `pywin32` in the venv, registers the `TransformersMPF.Controller` COM server
(Windows asks for administrator rights once) and, with `-Table`, writes the table's MPF script next to the
table. The `.vpx` is never changed. Details and the table to use: [vpx.md](vpx.md).

## The P-ROC (driver only)

`--proc` / `-Proc` prepares the driver as for Tron: on Windows the Visual C++ runtime and a check for FTDI's D2XX
driver, on macOS and Linux `scripts/install/build_pinproc.sh` (libpinproc, pypinproc) and on Linux the udev rule
`scripts/install/99-pinproc.rules`. The game's P-ROC numbers are generated (`game/config/rom/proc_numbers.yaml`),
but `run.py` has no `--hw proc` yet ([hardware.md](hardware.md)).

## Network

The first setup downloads from pypi.org (MPF and the Python packages), github.com (Godot, GMC, the PuP Pack
submodule) and raw.githubusercontent.com (MPF Monitor's `.ui` files), plus python.org, Homebrew, winget or your
distribution's mirrors depending on the route. At run time everything talks over localhost only: GMC on TCP
5050, MPF's BCP server for MPF Monitor on 5051.
