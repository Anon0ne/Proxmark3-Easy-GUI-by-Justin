"""Persistent PC slots and the single active Classic emulator buffer."""
import hashlib
import json
from pathlib import Path
import re
import uuid
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QTreeWidget,QTreeWidgetItem,
    QPlainTextEdit,QComboBox,QPushButton,QFileDialog,QMessageBox,QInputDialog,QSplitter,QTabWidget,QHeaderView,QScrollArea,QFrame)
from catalog import clean,validate_line
from eventlog import EventLogFormatter

SIZES = {'mini':320,'1k':1024,'2k':2048,'4k':4096}
SLOT_COUNT = 16

def inspect_dump(path):
    path = Path(path)
    if path.stat().st_size > 250_000: raise ValueError('Dump is too large for a Classic card.')
    uid = None
    if path.suffix.lower() == '.bin':
        data = path.read_bytes()
    elif path.suffix.lower() == '.eml':
        lines = [line.strip() for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        if any(not re.fullmatch(r'[0-9a-fA-F]{32}',line) for line in lines):
            raise ValueError('EML must contain one complete 16-byte block per line.')
        data = bytes.fromhex(''.join(lines))
    elif path.suffix.lower() == '.json':
        obj = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(obj,dict) or obj.get('FileType') not in {'mfc','mfc v2'}:
            raise ValueError('Select an Iceman MIFARE Classic JSON dump.')
        blocks = obj.get('blocks')
        if not isinstance(blocks,dict) or set(blocks) != {str(i) for i in range(len(blocks))}:
            raise ValueError('JSON blocks are missing or not contiguous.')
        values = [blocks[str(i)] for i in range(len(blocks))]
        if any(not isinstance(value,str) or not re.fullmatch(r'[0-9a-fA-F]{32}',value) for value in values):
            raise ValueError('JSON contains an incomplete or invalid block.')
        data = bytes.fromhex(''.join(values))
        card = obj.get('Card',{})
        uid = card.get('UID') if isinstance(card,dict) else None
        if uid is not None and (not isinstance(uid,str) or not re.fullmatch(r'(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{14}|[0-9a-fA-F]{20})',uid)):
            raise ValueError('JSON UID is invalid.')
    else: raise ValueError('Supported dump formats: BIN, EML and Iceman Classic JSON.')
    size = next((name for name,length in SIZES.items() if length == len(data)),None)
    if not size: raise ValueError('Expected a complete Classic Mini, 1K, 2K or 4K dump.')
    warnings = []
    for block in range(len(data)//16):
        trailer = block < 128 and block % 4 == 3 or block >= 128 and (block-128) % 16 == 15
        if not trailer: continue
        a,b,c = data[block*16+6:block*16+9]
        if ((a & 15) ^ (b >> 4)) != 15 or ((a >> 4) ^ (c & 15)) != 15 or ((b & 15) ^ (c >> 4)) != 15:
            warnings.append('Invalid access bits in trailer block '+str(block))
    return data,{'size':size,'bytes':len(data),'uid':uid.upper() if uid else data[:4].hex().upper(),
        'uid_source':'JSON metadata' if uid else 'block 0 first four bytes; verify UID length',
        'sha256':hashlib.sha256(data).hexdigest(),'warnings':warnings}

class SlotLibrary:
    def __init__(self,root):
        self.root = Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.path = self.root/'slots.json'; self.slots = {}; self.error = None
        try:
            if self.path.exists():
                saved = json.loads(self.path.read_text(encoding='utf-8'))
                if saved.get('version') != 1 or not isinstance(saved.get('slots'),dict): raise ValueError('Unsupported slot index.')
                for number,record in saved['slots'].items():
                    if number not in {str(i) for i in range(1,SLOT_COUNT+1)} or not isinstance(record,dict):
                        raise ValueError('Invalid slot entry.')
                    if not isinstance(record.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',record['sha256']):
                        raise ValueError('Invalid slot hash.')
                    if record.get('size') not in SIZES or not isinstance(record.get('name'),str): raise ValueError('Invalid slot metadata.')
                    if not isinstance(record.get('warnings',[]),list) or any(not isinstance(warning,str) for warning in record.get('warnings',[])): raise ValueError('Invalid slot warnings.')
                    self.slots[number] = record
        except (OSError,ValueError,TypeError,AttributeError) as error:
            self.error = str(error); self.slots = {}

    def persist(self,slots):
        if self.error: raise ValueError('Slot index cannot be read. Preserve it and repair before saving: '+self.error)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps({'version':1,'slots':slots},indent=2),encoding='utf-8')
        temp.replace(self.path); self.slots = slots

    def file(self,record):
        return self.root/'dumps'/(record['sha256']+'.bin')

    def verified(self,record):
        data,meta = inspect_dump(self.file(record))
        if meta['sha256'] != record['sha256'] or meta['size'] != record['size']:
            raise ValueError('Slot dump changed or is corrupted.')
        return data,meta

    def save(self,number,path,name):
        if number not in range(1,SLOT_COUNT+1): raise ValueError('Invalid slot number.')
        data,record = inspect_dump(path)
        record.update(name=name.strip()[:100] or 'Classic '+record['size'].upper(),saved=datetime.now().isoformat(timespec='seconds'))
        target = self.file(record); target.parent.mkdir(exist_ok=True)
        if not target.exists(): target.write_bytes(data)
        elif target.read_bytes() != data: raise ValueError('Stored dump hash mismatch.')
        slots = dict(self.slots); slots[str(number)] = record; self.persist(slots)
        return record

    def clear(self,number):
        if number not in range(1,SLOT_COUNT+1): raise ValueError('Invalid slot number.')
        slots = dict(self.slots); slots.pop(str(number),None); self.persist(slots)

def emulator_command(commands,operation,size,path=None,uid=None):
    names = {'load':'hf mf eload','capture':'hf mf esave','view':'hf mf eview','simulate':'hf mf sim','stop':'hw break'}
    name = names[operation]
    meta = commands.get(name)
    if not meta: raise ValueError('Installed client does not expose '+name+'.')
    if operation == 'stop': return name
    flags = {option.flag for option in meta.options}
    if size not in SIZES or '--'+size not in flags: raise ValueError('Installed client does not document this card size.')
    line = name+' --'+size
    if operation == 'simulate' and uid is not None:
        flag = '--uid' if '--uid' in flags else '-u' if '-u' in flags else None
        if not flag or not re.fullmatch(r'(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{14}|[0-9a-fA-F]{20})',uid):
            raise ValueError('Installed client lacks a supported UID option or the UID is invalid.')
        line += ' '+flag+' '+uid
    if path is not None:
        flag = '--file' if '--file' in flags else '-f' if '-f' in flags else None
        if not flag: raise ValueError('Installed client has no documented file option.')
        if any(char in path for char in '"\r\n;'): raise ValueError('Invalid dump path.')
        line += ' '+flag+' "'+path+'"'
    validate_line(line)
    return line

def output_failed(text):
    return bool(re.search(r'(?im)^\s*(?:\[!\]|\[-\]|(?:error|failed|can.t|timeout|time-out|no tag)\b)|\bonly loaded \d+ blocks\b',clean(text)))

def read_view_bytes(text,size):
    rows = {}
    for match in re.finditer(r'(?m)^\s*\[=\]\s*(?:\d+)?\s*\|\s*(\d+)\s*\|\s*((?:[0-9a-fA-F]{2}\s+){15}[0-9a-fA-F]{2})\s*\|',clean(text)):
        block = int(match[1])
        if block in rows: raise ValueError('Duplicate block in emulator view.')
        rows[block] = bytes.fromhex(match[2])
    expected = SIZES[size]//16
    if set(rows) != set(range(expected)): raise ValueError('Emulator view is incomplete; capture the buffer to a file instead.')
    return b''.join(rows[i] for i in range(expected))

def format_blocks(data):
    return '\n'.join(f'{block:03d}  '+data[block*16:(block+1)*16].hex().upper() for block in range(len(data)//16))

class EmulationPanel(QWidget):
    def __init__(self,owner):
        super().__init__(); self.owner = owner; self.pending = None
        self.active = None; self.simulating = False; self.recovered = None
        self.library = SlotLibrary(owner.data_dir/'emulation')
        layout = QVBoxLayout(self)
        note = QLabel('16 saved slots on this PC · one current emulator buffer on the device.\nClassic Mini / 1K / 2K / 4K dumps. Slots persist; device memory must be read or loaded again after reconnecting.')
        note.setWordWrap(True); layout.addWidget(note)
        self.active_label = QLabel('Device buffer: not inspected.'); self.active_label.setWordWrap(True); layout.addWidget(self.active_label)
        self.status = QLabel('Select a PC slot to import or save a card dump.'); self.status.setWordWrap(True); layout.addWidget(self.status)
        split = QSplitter(); layout.addWidget(split,1)
        left = QWidget(); lv = QVBoxLayout(left)
        self.table = QTreeWidget(); self.table.setHeaderLabels(['PC slot','Name','Type','UID / block 0','Integrity'])
        self.table.header().setStretchLastSection(False)
        self.table.header().setSectionResizeMode(1,QHeaderView.Stretch)
        for column in [0,2,3,4]: self.table.header().setSectionResizeMode(column,QHeaderView.ResizeToContents)
        self.table.setRootIsDecorated(False); self.table.itemSelectionChanged.connect(self.selection)
        lv.addWidget(self.table)
        local = QHBoxLayout(); lv.addLayout(local)
        for text,callback in [('Import dump…',self.import_dump),('Rename',self.rename),('Export…',self.export),('Clear slot',self.clear)]:
            button = QPushButton(text); button.clicked.connect(callback); local.addWidget(button)
        self.save_recovered = QPushButton('Save recovered dump to selected slot'); self.save_recovered.clicked.connect(self.save_recovery); self.save_recovered.setEnabled(False); lv.addWidget(self.save_recovered)
        split.addWidget(left)
        right = QWidget(); rv = QVBoxLayout(right)
        self.inspector = QTabWidget(); rv.addWidget(self.inspector,1)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True); self.inspector.addTab(self.details,'Slot details')
        self.slot_data = QPlainTextEdit(); self.slot_data.setReadOnly(True); self.slot_data.setFont(QFont('Consolas',10)); self.inspector.addTab(self.slot_data,'Slot data')
        self.device_view = QPlainTextEdit(); self.device_view.setReadOnly(True); self.device_view.setFont(QFont('Consolas',10)); self.inspector.addTab(self.device_view,'Device')
        self.size = QComboBox(); self.size.addItems(list(SIZES)); self.size.setCurrentText('1k'); self.size.setToolTip('Format for reading or capturing the current device buffer; it is not an automatic card-size detector.')
        rv.addWidget(QLabel('Current device buffer format')); rv.addWidget(self.size)
        self.buttons = {}
        for key,text,callback in [('view','Read memory',self.view),('capture','Save to slot',self.capture),
                                  ('load','Load slot & verify',self.load),('simulate','Simulate…',self.simulate),('stop','Stop simulation',self.stop_simulation)]:
            button = QPushButton(text); button.clicked.connect(callback); button.setMinimumHeight(40); self.buttons[key] = button
        read_actions = QHBoxLayout(); read_actions.addWidget(self.buttons['view']); read_actions.addWidget(self.buttons['capture']); rv.addLayout(read_actions)
        rv.addWidget(self.buttons['load'])
        sim_actions = QHBoxLayout(); sim_actions.addWidget(self.buttons['simulate']); sim_actions.addWidget(self.buttons['stop']); rv.addLayout(sim_actions)
        device_scroll = QScrollArea(); device_scroll.setWidgetResizable(True); device_scroll.setFrameShape(QFrame.NoFrame)
        right.setMinimumHeight(380); device_scroll.setWidget(right)
        split.addWidget(device_scroll); split.setSizes([760,400])
        self.refresh()

    def slot_number(self):
        item = self.table.currentItem()
        return item.data(0,Qt.UserRole) if item else 1

    def refresh(self):
        number = self.slot_number(); self.table.clear()
        for index in range(1,SLOT_COUNT+1):
            record = self.library.slots.get(str(index))
            integrity = 'Empty'
            if record:
                try:
                    _,meta = self.library.verified(record)
                    integrity = 'Needs review' if meta['warnings'] else 'Checked'
                    if self.active and self.active['sha256'] == record['sha256']: integrity += ' · loaded'
                except (OSError,ValueError): integrity = 'Missing / changed'
            item = QTreeWidgetItem([f'{index:02d}',record['name'] if record else 'Empty slot',
                'Classic '+record['size'].upper() if record else '',str(record.get('uid','')) if record else '',integrity])
            item.setData(0,Qt.UserRole,index); self.table.addTopLevelItem(item)
            if index == number: self.table.setCurrentItem(item)
        if self.library.error: self.status.setText('Slot index problem: '+self.library.error+' · original index preserved.')
        self.selection(); self.update_controls()

    def selection(self):
        record = self.library.slots.get(str(self.slot_number()))
        if record:
            try:
                data,_ = self.library.verified(record); self.slot_data.setPlainText(format_blocks(data))
            except (OSError,ValueError) as error: self.slot_data.setPlainText(str(error))
            self.details.setPlainText('PC slot '+str(self.slot_number())+'\n'+record['name']+'\nClassic '+record['size'].upper()+
                '\nUID / hint: '+str(record.get('uid',''))+'\n'+str(record.get('uid_source',''))+
                '\nSHA256: '+record['sha256']+'\n\n'+('\n'.join(record.get('warnings',[])) or 'Complete file size and valid access-bit complements. This does not prove every key or data block was recovered.'))
        else:
            self.details.setPlainText('Select this slot to import a dump or save current device memory.')
            self.slot_data.clear()
        self.update_controls()

    def update_controls(self):
        if not hasattr(self,'buttons'): return
        available = self.owner.session.ready and self.owner.compatible and self.owner.catalog_verified and not self.owner.firmware.busy and not self.owner.pending_info and not self.owner.pending_recovery and not self.owner.recovery_running and not self.owner.workflow_prompt and self.owner.workflow_stage != 'identifying' and not self.owner.queue
        record = self.library.slots.get(str(self.slot_number()))
        for key in self.buttons: self.buttons[key].setEnabled(available and not self.pending and not self.simulating)
        self.buttons['load'].setEnabled(available and not self.pending and not self.simulating and bool(record))
        self.buttons['simulate'].setEnabled(available and not self.pending and not self.simulating and bool(self.active))
        self.buttons['stop'].setEnabled(available and not self.pending and self.simulating)
        if self.simulating: self.active_label.setText('Device: simulation requested · use Stop simulation before other operations.')
        elif self.active:
            self.active_label.setText('Last verified device buffer: Classic '+self.active['size'].upper()+' · UID / hint '+str(self.active.get('uid',''))+' · slot '+str(self.active['slot'])+' · '+self.active['sha256'][:12])
        else: self.active_label.setText('Device buffer: unknown association. Read it, capture it, or load a saved slot.')

    def inform(self,error):
        self.status.setText(str(error))

    def save_file(self,path):
        number = self.slot_number()
        if str(number) in self.library.slots:
            if QMessageBox.question(self,'Replace PC slot?',f'Replace slot {number:02d}? The old dump file is retained locally.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No) != QMessageBox.Yes: return
        name,ok = QInputDialog.getText(self,'Name saved card','Slot name:',text=Path(path).stem)
        if not ok: return
        try:
            record = self.library.save(number,path,name); self.refresh()
            self.status.setText(f'Saved to PC slot {number:02d}. Device memory was not changed.')
            return record
        except (OSError,ValueError,TypeError) as error: self.inform(error)

    def import_dump(self):
        path,_ = QFileDialog.getOpenFileName(self,'Import Classic card dump','','Classic dumps (*.bin *.eml *.json)')
        if path: self.save_file(path)

    def rename(self):
        record = self.library.slots.get(str(self.slot_number()))
        if not record: return
        name,ok = QInputDialog.getText(self,'Rename PC slot','Name:',text=record['name'])
        if ok:
            try:
                slots = dict(self.library.slots); slots[str(self.slot_number())] = dict(record,name=name.strip()[:100] or record['name'])
                self.library.persist(slots); self.refresh()
            except (OSError,ValueError) as error: self.inform(error)

    def export(self):
        record = self.library.slots.get(str(self.slot_number()))
        if not record: return
        path,_ = QFileDialog.getSaveFileName(self,'Export canonical Classic dump','slot-'+str(self.slot_number())+'.bin','Binary dump (*.bin)')
        if path:
            try:
                data,_ = self.library.verified(record); Path(path).write_bytes(data)
                self.status.setText('Exported verified local dump.')
            except (OSError,ValueError) as error: self.inform(error)

    def clear(self):
        number = self.slot_number()
        if str(number) not in self.library.slots: return
        if QMessageBox.question(self,'Clear PC slot?',f'Clear slot {number:02d}? The device is untouched and the old dump file is retained.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No) != QMessageBox.Yes: return
        try: self.library.clear(number); self.refresh()
        except (OSError,ValueError) as error: self.inform(error)

    def send(self,operation,size,path=None,context=None,confirm=False):
        try:
            if not self.owner.session.ready or not self.owner.compatible or self.owner.queue or self.owner.firmware.busy: raise ValueError('Connect and verify the reader, then wait for it to be idle.')
            if self.owner.workflow_busy() and not (operation == 'stop' and self.simulating and not self.pending):
                raise ValueError('Finish the current card or emulator operation first.')
            uid = self.active.get('uid') if operation == 'simulate' and self.active and self.active.get('uid_source') == 'JSON metadata' else None
            line = emulator_command(self.owner.commands,operation,size,path,uid)
            if confirm:
                if self.owner.ask_workflow('Review emulator operation',line+'\n\n'+('This replaces the current device emulator buffer; PC slots and physical cards are unchanged.' if operation == 'load' else 'Emulate the loaded card on your authorized test reader. Stop simulation before other operations. No physical card write is queued.')) != QMessageBox.Yes: return False
            self.owner.approved_emulator = line
            self.owner.poll.stop(); self.owner.auto_detect.setChecked(False)
            if not self.owner.dispatch(line): return False
            self.pending = dict(operation=operation,size=size,context=context or {})
            self.status.setText('Running '+line+'…')
            self.owner.update_controls(); return True
        except (OSError,ValueError) as error: self.inform(error); return False

    def view(self):
        self.send('view',self.size.currentText())

    def capture_path(self):
        folder = self.owner.data_dir/'emu-captures'; folder.mkdir(exist_ok=True)
        relative = 'emu-captures/'+uuid.uuid4().hex
        return relative,self.owner.data_dir/(relative+'.bin')

    def capture(self):
        if self.pending or self.simulating: return
        try:
            relative,path = self.capture_path()
            self.send('capture',self.size.currentText(),relative,{'path':path,'slot':self.slot_number()})
        except OSError as error: self.inform(error)

    def load(self):
        record = self.library.slots.get(str(self.slot_number()))
        if not record: return
        try:
            _,meta = self.library.verified(record)
            if meta['warnings']: raise ValueError('Review invalid access bits before loading this dump.')
            relative = self.library.file(record).relative_to(self.owner.data_dir).as_posix()
            self.send('load',record['size'],relative,{'record':dict(record),'slot':self.slot_number()},True)
        except (OSError,ValueError) as error: self.inform(error)

    def simulate(self):
        if not self.active or self.pending or self.simulating: return
        try:
            uid = self.active.get('uid') if self.active.get('uid_source') == 'JSON metadata' else None
            line = emulator_command(self.owner.commands,'simulate',self.active['size'],uid=uid)
            if self.owner.ask_workflow('Review simulation',line+'\n\nRead back and verify the buffer again, then emulate this card on your authorized test reader? No physical card write or reader attack is queued. Use Stop simulation or the PM3 button to stop.') != QMessageBox.Yes: return
            relative,path = self.capture_path()
            self.send('capture',self.active['size'],relative,{'path':path,'simulate':dict(self.active)})
        except (OSError,ValueError) as error: self.inform(error)

    def stop_simulation(self):
        if self.simulating: self.send('stop',self.size.currentText())

    def completed(self,command,text):
        if not self.pending:
            if command.startswith('hf mf sim ') and not output_failed(text) and re.search(r'send another cmd to abort simulation',clean(text),re.I):
                self.simulating = True; self.active = None
                self.status.setText('Simulation requested from the workbench. Use Stop simulation before another task; buffer association is unknown.')
                self.owner.update_controls()
            return
        operation = self.pending['operation']
        name = {'load':'hf mf eload','capture':'hf mf esave','view':'hf mf eview','simulate':'hf mf sim','stop':'hw break'}[operation]
        if not (command == name or command.startswith(name+' ')): return
        pending = self.pending; self.pending = None
        if output_failed(text):
            self.status.setText('Emulator operation reported a failure. Inspect Console before retrying.')
            if operation in {'load','simulate','stop'}: self.active = None
            self.owner.update_controls(); return
        context = pending['context']
        if operation == 'view':
            self.active = None
            self.device_view.setPlainText(EventLogFormatter().feed(text+'\n'))
            self.inspector.setCurrentWidget(self.device_view)
            try:
                data = read_view_bytes(text,pending['size'])
                self.device_view.setPlainText(format_blocks(data))
                digest = hashlib.sha256(data).hexdigest()
                matches = []
                for number,record in self.library.slots.items():
                    if record['sha256'] != digest: continue
                    _,meta = self.library.verified(record)
                    if meta['warnings']: continue
                    matches.append(number)
                    if self.active is None: self.active = dict(record,slot=int(number))
                self.status.setText('Device buffer matches PC slot(s): '+', '.join(matches) if matches else 'Device buffer read; no saved slot matches. Capture it to a PC slot if needed.')
            except (OSError,ValueError) as error: self.inform(error)
        elif operation == 'load':
            self.active = None
            relative,path = self.capture_path()
            self.send('capture',pending['size'],relative,{'path':path,'verify':context})
        elif operation == 'capture':
            try:
                _,meta = inspect_dump(context['path'])
                if meta['size'] != pending['size']: raise ValueError('Captured memory size does not match the selected format.')
                if 'verify' in context:
                    verified = context['verify']
                    if meta['sha256'] != verified['record']['sha256']: raise ValueError('Device read-back differs from the slot dump. Simulation is blocked.')
                    self.active = dict(verified['record'],slot=verified['slot'])
                    self.size.setCurrentText(pending['size'])
                    self.status.setText(f'Device read-back verified against PC slot {verified["slot"]:02d}. Ready to review simulation.')
                    self.refresh()
                elif 'simulate' in context:
                    if meta['sha256'] != context['simulate']['sha256']: raise ValueError('Device memory changed since loading. Simulation canceled; reload the intended slot.')
                    self.send('simulate',pending['size'])
                else:
                    self.table.setCurrentItem(self.table.topLevelItem(context['slot']-1))
                    save_path = context['path']
                    sidecar = save_path.with_suffix('.json')
                    if sidecar.exists():
                        _,json_meta = inspect_dump(sidecar)
                        if json_meta['sha256'] != meta['sha256']: raise ValueError('Capture JSON and binary data differ.')
                        save_path = sidecar
                    record = self.save_file(save_path)
                    if record and not meta['warnings']:
                        self.active = dict(record,slot=context['slot']); self.refresh()
                        self.status.setText(f'Device capture saved and verified in PC slot {context["slot"]:02d}. Simulation requires separate review.')
            except (OSError,ValueError) as error: self.active = None; self.inform(error)
        elif operation == 'simulate':
            self.simulating = True
            self.status.setText('Simulation requested. Stop simulation or press the PM3 button before other operations. Reader interaction is not verified by command completion.')
        elif operation == 'stop':
            self.simulating = False; self.active = None
            self.status.setText('Break command completed. Read or reload device memory before another simulation.')
        self.owner.update_controls()

    def invalidate(self,message='Device buffer association invalidated; read or reload it.'):
        self.pending = None; self.active = None; self.simulating = False
        self.status.setText(message); self.update_controls()

    def offer_recovered(self,text,card):
        if not card: return
        for match in re.finditer(r"Saved\s+(\d+)\s+bytes to binary file\s+[`']([^`'\r\n]+)[`']",clean(text)):
            path = Path(match[2])
            if not path.is_absolute(): path = self.owner.data_dir/path
            try:
                data,meta = inspect_dump(path)
                if meta['size'] != card.size or meta['warnings']: continue
                if len(card.uid) == 8 and data[:4].hex().upper() != card.uid: continue
                if len(card.uid) != 8:
                    _,sidecar = inspect_dump(path.with_suffix('.json'))
                    if sidecar['uid_source'] != 'JSON metadata' or sidecar['uid'] != card.uid or sidecar['sha256'] != meta['sha256']: continue
                    path = path.with_suffix('.json')
                self.recovered = path; self.save_recovered.setEnabled(True)
                self.save_recovered.setText('Save recovered '+card.uid+' to selected slot')
                self.status.setText('A complete-size recovery dump is available to save to a PC slot. Review its recovery results before use.')
                return True
            except (OSError,ValueError): continue
        return False

    def save_recovery(self):
        if self.recovered: self.save_file(self.recovered)

    def clear_recovery_offer(self):
        self.recovered = None; self.save_recovered.setEnabled(False)
        self.save_recovered.setText('Save recovered dump to selected slot')

    def offer_save_recovery(self):
        if not self.recovered: return
        if QMessageBox.question(self,'Save recovery dump to a PC slot?','A complete-size dump file is available. Review its recovery results; file size alone does not prove all data or keys were recovered.\n\nSave it to a persistent PC slot now?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No) != QMessageBox.Yes: return
        default = next((number for number in range(1,SLOT_COUNT+1) if str(number) not in self.library.slots),1)
        number,ok = QInputDialog.getInt(self,'Choose PC slot','Slot number (existing contents require replacement confirmation):',default,1,SLOT_COUNT)
        if not ok: return
        self.table.setCurrentItem(self.table.topLevelItem(number-1))
        self.owner.tabs.setCurrentWidget(self)
        self.save_file(self.recovered)
