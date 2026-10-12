"""Package a native Linux build with a per-user launcher installer."""
from pathlib import Path
import tarfile
from app import VERSION
root = Path(__file__).resolve().parent
target = root.parent/'release'/f'Proxmark3-Easy-GUI-{VERSION}-Linux-x86_64.tar.gz'
target.parent.mkdir(exist_ok=True)
with tarfile.open(target,'w:gz') as archive:
    for source,name in [('dist-linux/Proxmark3Suite','Proxmark3Suite'),('assets/app-icon.png','app-icon.png'),('install_linux.sh','install.sh'),('LINUX.md','README.md')]:
        archive.add(root/source,arcname='Proxmark3EasyGUI/'+name)
print(target)
