#!/bin/sh
set -eu
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
destination="$HOME/.local/opt/Proxmark3EasyGUI"
mkdir -p "$destination" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/256x256/apps"
install -m 755 "$source_dir/Proxmark3Suite" "$destination/Proxmark3Suite"
install -m 644 "$source_dir/app-icon.png" "$HOME/.local/share/icons/hicolor/256x256/apps/proxmark3-easy-gui.png"
python3 - "$destination" "$HOME/.local/share/applications/proxmark3-easy-gui.desktop" <<'PY'
import sys
from pathlib import Path
exe=str(Path(sys.argv[1])/'Proxmark3Suite')
# Desktop Entry quoted Exec values have different escaping from shell quoting.
exe=exe.replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
Path(sys.argv[2]).write_text('[Desktop Entry]\nType=Application\nName=Proxmark3 Engineering Suite\nExec="'+exe+'"\nIcon=proxmark3-easy-gui\nTerminal=false\nCategories=Utility;\n',encoding='utf-8')
PY
printf 'Installed app: %s\nLaunch from your application menu.\n' "$destination/Proxmark3Suite"
