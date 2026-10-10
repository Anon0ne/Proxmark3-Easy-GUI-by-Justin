"""One persistent client with serialized, random-marker-delimited transactions."""
import codecs
import os
from pathlib import Path
import re
import uuid
import sys
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal
from catalog import clean, validate_line

def start_external(process):
    # PyInstaller's inherited DLL directory can load the suite's Qt into an
    # external Iceman client built against a different Qt version.
    if sys.platform == 'win32' and getattr(sys,'frozen',False):
        import ctypes
        ctypes.windll.kernel32.SetDllDirectoryW(None)
        try:
            process.start()
        finally:
            ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)
    else:
        process.start()

def client_environment(exe, runtime_bin=''):
    env = QProcessEnvironment.systemEnvironment()
    libs = str(Path(exe).parent / 'libs')
    env.insert('PATH', libs + os.pathsep + str(Path(libs) / 'shell') + os.pathsep + env.value('PATH'))
    if runtime_bin:
        env.insert('PATH', runtime_bin + os.pathsep + env.value('PATH'))
    # Isolate the external client's plugins from PySide's Qt distribution.
    plugins = libs if not runtime_bin else str(Path(runtime_bin).parent / 'share/qt6/plugins')
    env.insert('QT_PLUGIN_PATH', plugins)
    env.insert('QT_QPA_PLATFORM_PLUGIN_PATH', plugins)
    env.remove('QT_QPA_PLATFORM')
    return env

def resolve_client(path):
    path = Path(path)
    if path.suffix.lower() == '.bat':
        path = path.parent / 'client' / 'proxmark3.exe'
    if not path.is_file() or path.suffix.lower() != '.exe':
        raise ValueError('Choose pm3.bat with a sibling client/proxmark3.exe, or the client executable.')
    return str(path)

class Session(QObject):
    output = Signal(str)
    state = Signal(str)
    completed = Signal(str, str)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.errorOccurred.connect(self.process_error)
        self.process.finished.connect(self.finished)
        self.process.started.connect(self.handshake)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.abort('Client response timed out. Session closed; reconnect before retrying.'))
        self.ready = False
        self.active = None
        self.buffer = ''
        self.decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self.marker = ''
        self.stopping = False
        self.command_timeout_ms = 180000

    def process_error(self, error):
        if not self.stopping:
            self.abort(self.process.errorString())

    def handshake(self):
        # Pipe mode suppresses idle prompts. The upstream `rem` command emits a
        # remark, establishing a fence after startup and each executed command.
        self.marker = 'SUITE_' + uuid.uuid4().hex
        self.process.write(('rem ' + self.marker + '\n').encode())

    def start(self, exe, port, workdir, offline=False, runtime_bin=''):
        if self.process.state() != QProcess.NotRunning:
            raise ValueError('Disconnect the current session first.')
        if not re.fullmatch(r'COM\d+', port, re.I):
            raise ValueError('Port must be COM followed by its number.')
        self.buffer = ''
        self.active = None
        self.ready = False
        self.stopping = False
        self.decoder.reset()
        self.process.setProgram(exe)
        self.process.setArguments(([] if offline else ['-p', port]) + ['-f', '--incognito', '-i'])
        self.process.setProcessEnvironment(client_environment(exe, runtime_bin))
        self.process.setWorkingDirectory(str(workdir))
        self.state.emit('Connecting')
        start_external(self.process)
        self.timer.start(25000)

    def send(self, line):
        validate_line(line)
        if not self.ready or self.active:
            raise ValueError('Client is disconnected or busy.')
        self.ready = False
        self.active = line
        self.buffer = ''
        self.state.emit('Running: ' + line)
        self.marker = 'SUITE_' + uuid.uuid4().hex
        self.process.write((line + '\nrem ' + self.marker + '\n').encode())
        self.timer.start(self.command_timeout_ms)

    def read(self):
        text = self.decoder.decode(bytes(self.process.readAllStandardOutput()))
        self.output.emit(text)
        self.buffer += clean(text)
        if re.search(r'remark:\s*' + re.escape(self.marker) + r'\s*\n',self.buffer):
            self.timer.stop()
            result = re.sub(r'(?m)^.*remark:\s*' + re.escape(self.marker) + r'.*\n?', '', self.buffer)
            self.buffer = ''
            command = self.active
            self.active = None
            self.ready = True
            self.state.emit('Ready')
            if command:
                self.completed.emit(command, result)

    def abort(self, reason):
        self.timer.stop()
        self.ready = False
        self.active = None
        self.stopping = True
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()
        self.failed.emit(reason)

    def stop(self):
        self.abort('Session stopped. Reconnect to continue; an operation already sent cannot be undone.')

    def finished(self, code, status):
        self.timer.stop()
        self.ready = False
        self.active = None
        self.state.emit('Disconnected')
        if code and not self.stopping:
            self.failed.emit(f'Client exited with code {code}. Check port, DLLs, and firmware compatibility.')
