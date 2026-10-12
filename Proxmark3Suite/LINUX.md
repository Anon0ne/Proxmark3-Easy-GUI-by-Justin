# Linux x86_64 beta

Extract the tar.gz and run `./Proxmark3EasyGUI/Proxmark3Suite`. The executable bundles Python and Qt. It requires a Linux graphical desktop and system Qt/X11 libraries; Ubuntu 24.04 x86_64 is the build/test baseline. Other distributions and ARM are not verified.

Optionally run `sh Proxmark3EasyGUI/install.sh` to copy the app into `~/.local/opt/Proxmark3EasyGUI` and add an application-menu launcher/icon. The optional installer uses system Python 3 to safely generate the launcher. No sudo is needed for this installer.

Install or compile the matching native Iceman/RRG client separately. In Settings select its executable (for example `/usr/local/bin/proxmark3` or a compiled `client/proxmark3`) and the reader device (`/dev/ttyACM0`, `/dev/ttyUSB0` or `/dev/serial/by-id/...`). Use Find installed client & ports, then Connect & verify. Your account must have serial access; use your distribution's serial group/udev instructions rather than running the GUI as root.

GUI firmware build/flashing currently uses Windows ProxSpace and is disabled on Linux. Use the [upstream Linux instructions](https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/md/Installation_Instructions/Linux-Installation-Instructions.md) for firmware maintenance, then select the matching client.

Linux CI tests and packaged self-test do not access physical hardware. Windows device results are not Linux hardware verification. The self-test uses the captured command fixture. Recovery, writes, emulator load/RF interaction and firmware flashing remain unverified end to end.

Uninstall by removing `~/.local/opt/Proxmark3EasyGUI`, the `proxmark3-easy-gui.desktop` entry under `~/.local/share/applications`, and its icon under `~/.local/share/icons/hicolor/256x256/apps`. Saved card data/settings are separate and remain preserved.
