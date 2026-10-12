"""Isolated RRG source builds and explicitly confirmed fullimage flashing."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import uuid
from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QPlainTextEdit,QMessageBox,QFileDialog
from backend import client_environment,start_external

REPO = 'https://github.com/RfidResearchGroup/proxmark3.git'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build_script(path):
    posix = '/' + path.drive[0].lower() + str(path)[2:].replace('\\','/')
    return ('export PATH=/mingw64/bin:/usr/bin:$PATH; cd ' + shlex.quote(posix) +
            ' && command -v arm-none-eabi-gcc && command -v make && make clean && make -j2 PLATFORM=PM3GENERIC LED_ORDER=PM3EASY')

class FirmwarePanel(QWidget):
    def __init__(self, owner):
        super().__init__(); self.owner = owner; self.busy = False; self.staged = None
        layout = QVBoxLayout(self)
        note = QLabel('Iceman / RRG firmware workspace\n“latest” resolves the repository’s default branch to an exact commit. Each build uses a new checkout.\nBuild target: PM3GENERIC, Easy LED order, 512 KB. A configured ProxSpace toolchain is required.\nFlashing updates the fullimage only. Bootloader flashing is deliberately a separate manual maintenance procedure.')
        note.setWordWrap(True); layout.addWidget(note)
        self.ref = QLineEdit('latest'); self.ref.setPlaceholderText('latest or upstream release tag / branch')
        self.toolchain = QLineEdit(owner.settings.value('toolchain',r'C:\Users\Funde\Downloads\ProxSpace-3.12\msys2'))
        layout.addWidget(QLabel('Upstream revision')); layout.addWidget(self.ref)
        layout.addWidget(QLabel('ProxSpace MSYS2 directory')); layout.addWidget(self.toolchain)
        browse = QPushButton('Choose toolchain…'); browse.clicked.connect(self.browse); layout.addWidget(browse)
        actions = QHBoxLayout(); layout.addLayout(actions)
        self.prepare = QPushButton('Download & build revision'); self.prepare.clicked.connect(self.stage); actions.addWidget(self.prepare)
        self.flash_button = QPushButton('Review & install staged firmware'); self.flash_button.setEnabled(False); self.flash_button.clicked.connect(self.flash); actions.addWidget(self.flash_button)
        self.output = QPlainTextEdit(); self.output.setReadOnly(True); layout.addWidget(self.output)
        self.process = QProcess(self); self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(lambda _: self.fail(self.process.errorString()))
        self.steps = []; self.accumulated = ''; self.callback = None

    def browse(self):
        path = QFileDialog.getExistingDirectory(self,'Select ProxSpace msys2 directory')
        if path: self.toolchain.setText(path)

    def log(self,text):
        self.output.insertPlainText(text); self.owner.logger.info(text.rstrip())

    def read(self):
        text = bytes(self.process.readAllStandardOutput()).decode('utf-8','replace'); self.accumulated += text; self.log(text)

    def run(self,program,args,cwd,callback):
        self.callback = callback; self.accumulated = ''
        self.process.setProgram(str(program)); self.process.setArguments(args); self.process.setWorkingDirectory(str(cwd))
        runtime = self.owner.runtime_bin
        if self.staged and str(program) == self.staged['client']:
            runtime = str(Path(self.staged['toolchain'])/'mingw64/bin')
        env = client_environment(program,runtime)
        if 'bash' in str(program).lower(): env.insert('MSYSTEM','MINGW64'); env.insert('CHERE_INVOKING','1')
        self.process.setProcessEnvironment(env); start_external(self.process)

    def finished(self,code,status):
        self.read()
        callback = self.callback; self.callback = None
        if not self.busy: return
        if code != 0 or status != QProcess.NormalExit: self.fail(f'Operation failed, exit code {code}. No client switch performed.'); return
        if callback:
            try: callback(self.accumulated)
            except (OSError,ValueError) as error: self.fail(str(error))

    def fail(self,message):
        self.log('\n[ERROR] '+message+'\n'); self.busy = False; self.prepare.setEnabled(True); self.flash_button.setEnabled(False); self.staged = None

    def stage(self):
        if self.busy: return
        if self.owner.workflow_busy() or self.owner.session.active:
            self.owner.statusBar().showMessage('Finish or stop the current client operation before building firmware.'); return
        ref = self.ref.text().strip()
        if ref != 'latest' and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*',ref): self.fail('Enter latest or a valid upstream branch/tag.'); return
        bash = Path(self.toolchain.text())/'usr/bin/bash.exe'
        if not bash.is_file(): self.fail('ProxSpace bash.exe not found. Install/configure ProxSpace first.'); return
        self.staged = None; self.flash_button.setEnabled(False); self.busy = True; self.prepare.setEnabled(False)
        self.owner.settings.setValue('toolchain',self.toolchain.text())
        checkout = self.owner.data_dir/'firmware'/uuid.uuid4().hex
        checkout.parent.mkdir(parents=True,exist_ok=True)
        # Full history keeps git-describe version/count metadata consistent with
        # upstream builds, rather than fabricating a version from a shallow clone.
        args = ['clone']
        if ref != 'latest': args += ['--branch',ref]
        args += [REPO,str(checkout)]
        def cloned(_):
            self.run('git',['rev-parse','HEAD'],checkout,resolved)
        def resolved(text):
            sha = text.strip()
            if not re.fullmatch(r'[a-f0-9]{40}',sha): self.fail('Could not resolve a unique commit.'); return
            self.log('\nResolved commit: '+sha+'\n')
            (checkout/'Makefile.platform').write_text('PLATFORM=PM3GENERIC\nLED_ORDER=PM3EASY\n',encoding='ascii')
            self.run(bash,['--noprofile','--norc','-c',build_script(checkout)],checkout,lambda _: built(sha))
        def built(sha):
            client = checkout/'client/proxmark3.exe'; image = checkout/'armsrc/obj/fullimage.elf'
            if not client.is_file() or not image.is_file(): self.fail('Expected client/fullimage build artifacts are missing.'); return
            # Use matching MSYS2 runtime libraries for the freshly compiled client.
            manifest = {'commit':sha,'platform':'PM3GENERIC','size':512,'client':str(client),'image':str(image),
                        'client_sha256':digest(client),'image_sha256':digest(image),'toolchain':self.toolchain.text()}
            (checkout/'suite-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
            self.staged = manifest
            def validated(text):
                revision = re.search(r'v\d+\.\d+-\d+-g([0-9a-f]+)',text)
                if not revision or not sha.startswith(revision.group(1)):
                    self.fail('Built client revision does not match the recorded source commit.'); return
                manifest['revision'] = revision.group()
                (checkout/'suite-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
                self.busy = False; self.prepare.setEnabled(True); self.flash_button.setEnabled(True)
                self.log('\nBuild staged for review. Firmware has not been flashed.\n'+json.dumps(manifest,indent=2)+'\n')
            self.run(client,['--incognito','--version'],checkout,validated)
        self.run('git',args,checkout.parent,cloned)

    def flash(self):
        if self.busy or not self.staged: return
        if self.owner.workflow_busy():
            self.owner.statusBar().showMessage('Finish or stop the current card workflow before flashing firmware.'); return
        if not self.owner.session.ready or self.owner.port.currentText() != getattr(self.owner,'session_port','') or getattr(self.owner,'session_offline',True):
            QMessageBox.warning(self,'Live verification required','Connect to the intended port and run hardware diagnostics before installing firmware.'); return
        manifest = self.staged
        version = self.owner.device_version
        if not re.search(r'PM3\s*GENERIC',version,re.I) or not re.search(r'AT91SAM7S512|512\s*(?:KB|Kbytes)',version+' '+getattr(self.owner,'device_status',''),re.I):
            QMessageBox.warning(self,'Hardware verification required','Connect and run hardware diagnostics first. This build requires a verified PM3 GENERIC board with 512 KB flash.'); return
        try:
            if digest(manifest['client']) != manifest['client_sha256'] or digest(manifest['image']) != manifest['image_sha256']: raise ValueError('Build artifact hashes changed; rebuild before flashing.')
        except (OSError,ValueError) as error: self.fail(str(error)); return
        answer = QMessageBox.question(self,'Confirm firmware installation','Install fullimage on '+self.owner.port.currentText()+'?\n\nPM3 GENERIC / 512 KB\nCommit: '+manifest['commit']+'\nImage SHA256: '+manifest['image_sha256']+'\n\nFirmware installation can make the device unusable if interrupted. Keep USB power connected. The bootloader is not modified.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer != QMessageBox.Yes: return
        self.owner.stop(); self.owner.session.process.waitForFinished(3000)
        self.busy = True; self.prepare.setEnabled(False); self.flash_button.setEnabled(False)
        client = manifest['client']
        def flashed(text):
            # Exit zero alone is insufficient; require the upstream success marker.
            if not re.search(r'\[\+\].*All done',text,re.I): self.fail('Flash success marker missing. Verify the device manually; client was not switched.'); return
            self.run(client,['--incognito','--version'],Path(client).parent,switched)
        def switched(text):
            revision = re.search(r'v\d+\.\d+-\d+-g[0-9a-f]+',text)
            if not revision: self.fail('New client revision could not be read.'); return
            self.owner.settings.setValue('previous_launcher',self.owner.launcher.text())
            self.owner.runtime_bin = str(Path(manifest['toolchain'])/'mingw64/bin')
            self.owner.settings.setValue('expected',revision.group()); self.owner.expected = revision.group()
            self.owner.settings.setValue('runtime_bin',self.owner.runtime_bin)
            self.owner.launcher.setText(client); self.owner.settings.setValue('launcher',client)
            self.busy = False; self.prepare.setEnabled(True)
            self.owner.reconnect_after_discovery = True
            self.owner.invalidate(); self.owner.discover()
            self.log('\nFirmware installation completed; matching client selected. Refreshing commands and reconnecting to verify on-device compatibility.\n')
        self.run(client,['-p',self.owner.port.currentText(),'--flash','--image',manifest['image']],Path(client).parent,flashed)
