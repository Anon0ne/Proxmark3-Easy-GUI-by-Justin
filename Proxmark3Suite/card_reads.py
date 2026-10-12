"""Confirmed, UID-checked Classic reads with explicit partial-result records."""
from pathlib import Path
import hashlib
import json
import re
import uuid
from datetime import datetime,timezone
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QComboBox,QPushButton,QPlainTextEdit,QMessageBox,QFileDialog
from catalog import clean,validate_line
from recovery import card_uid
from emulation import SIZES

def selected_blocks(expression,count):
    if expression.strip()=='*': return list(range(count))
    blocks=set()
    for part in expression.split(','):
        match=re.fullmatch(r'\s*(\d+)(?:\s*-\s*(\d+))?\s*',part)
        if not match: raise ValueError('Use block numbers/ranges such as 0-3,8,12 or * for all blocks.')
        start=int(match[1]); end=int(match[2] or match[1])
        if not 0<=start<=end<count: raise ValueError('Block range is outside the selected card size.')
        blocks.update(range(start,end+1))
    if not blocks: raise ValueError('Select at least one block.')
    return sorted(blocks)

def read_command(commands,block,key_type,key):
    if not isinstance(block,int) or not 0<=block<=255: raise ValueError('Invalid block number.')
    if key_type not in ('A','B') or not re.fullmatch('[0-9a-fA-F]{12}',key): raise ValueError('Supply Key A or B and exactly 12 hexadecimal key characters.')
    meta=commands.get('hf mf rdbl')
    flags={option.flag for option in meta.options} if meta else set()
    flag='-a' if key_type=='A' else '-b'
    if not {'--blk','--key',flag}<=flags or 'hf 14a reader' not in commands:
        raise ValueError('The installed client lacks the documented read/key/UID-check options.')
    line=f'hf mf rdbl --blk {block} {flag} --key {key.upper()}'
    validate_line(line); return line

def read_payload(text,block):
    text=clean(text)
    if re.search(r'(?im)\[-\]|no tag|auth.*(?:error|fail)|failed|communication error|timeout|can.t select',text): return None
    values=set()
    # Exact installed-client mf_print_block_one layout: decimal block | 16 bytes | ASCII.
    for line in text.splitlines():
        line=re.sub(r'^\s*\[[^]]+\]\s*','',line)
        match=re.match(r'^\s*(\d+)\s*\|\s*((?:[0-9a-fA-F]{2}\s+){15}[0-9a-fA-F]{2})(?:\s*\||\s*$)',line)
        if match and int(match[1])==block: values.add(bytes.fromhex(match[2]))
    return next(iter(values)) if len(values)==1 else None

def export_capture(report,directory):
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    token='classic-read-'+uuid.uuid4().hex
    record=dict(report)
    blocks=record['blocks']; count=SIZES[record['size']]//16
    complete=set(blocks)=={str(i) for i in range(count)} and all(value.get('status')=='read' and value.get('verified') is True for value in blocks.values())
    record['complete_card_data']=complete
    record['recovered_keys_complete']=False
    record['note']='Read data may mask trailer keys. Read completion is not complete key recovery.'
    if complete:
        payload=b''.join(bytes.fromhex(blocks[str(i)]['data']) for i in range(count))
        data_path=directory/(token+'.bin'); data_path.write_bytes(payload)
        if data_path.read_bytes()!=payload: raise OSError('Saved data did not match the verified capture.')
        record['data_file']=data_path.name; record['sha256']=hashlib.sha256(payload).hexdigest()
    else: record['data_file']=None
    path=directory/(token+'.json'); temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record,indent=2),encoding='utf-8'); temporary.replace(path)
    return path

class CardReadPanel(QWidget):
    def __init__(self,owner):
        super().__init__(); self.owner=owner; self.pending=None; self.report=None; self.todo=[]; self.expected=''; self.key_value=''; self.cancel_requested=False
        layout=QVBoxLayout(self); note=QLabel('Read selected Classic blocks using a supplied key. Identify the card first. Each block is preceded by a UID check; failed/unread blocks remain explicit. These operations do not write a card.')
        note.setWordWrap(True); layout.addWidget(note)
        row=QHBoxLayout(); layout.addLayout(row)
        self.size=QComboBox(); self.size.addItems(list(SIZES)); self.size.setCurrentText('1k')
        self.blocks=QLineEdit('0-3'); self.blocks.setPlaceholderText('0-3,8,12 or *')
        self.key_type=QComboBox(); self.key_type.addItems(['A','B'])
        self.key=QLineEdit(); self.key.setEchoMode(QLineEdit.Password); self.key.setPlaceholderText('12 hex key characters'); self.key.setMaxLength(12)
        for title,widget in [('Size',self.size),('Blocks',self.blocks),('Key type',self.key_type),('Key',self.key)]: row.addWidget(QLabel(title)); row.addWidget(widget)
        actions=QHBoxLayout(); layout.addLayout(actions)
        self.start_button=QPushButton('Review & read selected blocks'); self.start_button.clicked.connect(self.start); actions.addWidget(self.start_button)
        self.cancel_button=QPushButton('Cancel remaining reads'); self.cancel_button.clicked.connect(self.cancel); actions.addWidget(self.cancel_button)
        save=QPushButton('Export read report…'); save.clicked.connect(self.export); actions.addWidget(save)
        self.status=QLabel('No read capture yet. Reports contain private card data; keep them local.'); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.results=QPlainTextEdit(); self.results.setReadOnly(True); layout.addWidget(self.results,1)
        self.update_controls()

    def update_controls(self):
        busy=bool(self.pending)
        self.start_button.setEnabled(not busy); self.cancel_button.setEnabled(busy)
        for widget in (self.size,self.blocks,self.key_type,self.key): widget.setEnabled(not busy)

    def start(self):
        try:
            o=self.owner
            if o.workflow_busy() or not o.session.ready or not o.compatible or not o.catalog_verified or o.queue or o.firmware.busy or o.offline.isChecked(): raise ValueError('Connect and verify the reader, identify the intended Classic card, and wait for it to be idle.')
            card=o.recovery_card
            if not card or card.uid!=o.current_uid or card.size!=self.size.currentText(): raise ValueError('Identify a Classic card and select its detected size before reading.')
            blocks=selected_blocks(self.blocks.text(),SIZES[card.size]//16)
            key=self.key.text(); key_type=self.key_type.currentText()
            lines=[read_command(o.commands,b,key_type,key) for b in blocks]
            if o.ask_workflow('Confirm read-only capture',f'UID: {card.uid}\nClassic {card.size.upper()}\nBlocks: '+', '.join(map(str,blocks))+f'\nKey type: {key_type}\n\nRead with the supplied key and verify UID before every block? Reports may contain private data. No card writes are requested.')!=QMessageBox.Yes: return
            self.report={'schema':1,'uid':card.uid,'size':card.size,'started':datetime.now(timezone.utc).isoformat(),'client':o.client_version,'firmware':o.device_version,'requested_blocks':blocks,'key_type':key_type,'blocks':{},'status':'running'}
            self.todo=list(zip(blocks,lines)); self.key_value=key; self.cancel_requested=False
            self.render()
            self.next_block()
        except ValueError as error: self.status.setText(str(error))

    def send(self,line):
        self.expected=line; self.owner.approved_card_read=line
        self.owner.poll.stop(); self.owner.auto_detect.setChecked(False)
        if not self.owner.dispatch(line): self.abort('Client refused the capture command.'); return False
        self.owner.update_controls(); return True

    def next_block(self):
        if not self.report or self.report['status']!='running': return
        if self.cancel_requested or not self.todo:
            self.finish('canceled' if self.cancel_requested else 'completed'); return
        block,line=self.todo.pop(0); self.pending={'block':block,'line':line,'phase':'uid'}
        self.update_controls(); self.send('hf 14a reader')

    def completed(self,command,text):
        if not self.pending or command!=self.expected: return False
        block=self.pending['block']
        if self.pending['phase'] in ('uid','verify_uid'):
            if card_uid(text)!=self.report['uid'] or re.search(r'no tag|failed|communication error|can.t select',clean(text),re.I):
                self.abort('Card is missing or UID changed. Remaining blocks were not read.'); return True
            if self.cancel_requested: self.finish('canceled'); return True
            self.pending['phase']='read' if self.pending['phase']=='uid' else 'verify'; self.send(self.pending['line']); return True
        data=read_payload(text,block)
        if data is not None and self.pending['phase']=='read':
            self.pending['candidate']=data; self.pending['phase']='verify_uid'
            if self.cancel_requested: self.finish('canceled'); return True
            self.send('hf 14a reader'); return True
        verified=data is not None and data==self.pending.get('candidate')
        self.report['blocks'][str(block)]={'status':'read','data':data.hex().upper(),'verified':True} if verified else {'status':'failed','reason':'Read missing, ambiguous or different on verification; inspect Console.','verified':False}
        self.render(); QTimer.singleShot(0,self.next_block); return True

    def render(self):
        if not self.report: return
        lines=[f'UID: {self.report["uid"]} · Classic {self.report["size"].upper()} · supplied Key {self.report["key_type"]}\n']
        for block in self.report['requested_blocks']:
            value=self.report['blocks'].get(str(block),{'status':'unread'})
            lines.append(f'{block:3d} | {value["status"]:6s} | '+value.get('data',value.get('reason','')))
        self.results.setPlainText('\n'.join(lines))
        good=sum(v['status']=='read' for v in self.report['blocks'].values())
        self.status.setText(f'{self.report["status"]}: {good}/{len(self.report["requested_blocks"])} blocks verified by two matching reads. Unknown blocks are not zero-filled; trailer keys may be masked.')

    def finish(self,status):
        if status=='completed' and self.report and any(v['status']!='read' for v in self.report['blocks'].values()): status='partial'
        if self.report: self.report['status']=status; self.report['finished']=datetime.now(timezone.utc).isoformat()
        self.pending=None; self.expected=''; self.todo=[]; self.key_value=''; self.key.clear(); self.owner.approved_card_read=None
        self.render(); self.update_controls(); self.owner.update_controls()

    def abort(self,message):
        if not self.pending: return
        if self.report: self.report['error']=message
        self.finish('interrupted'); self.status.setText(message)

    def cancel(self):
        self.cancel_requested=True; self.status.setText('Cancel requested. Waiting for the active read/check to finish; remaining blocks will stay unread.')

    def export(self):
        if not self.report or self.pending: self.status.setText('Finish or cancel the capture before exporting.'); return
        directory=QFileDialog.getExistingDirectory(self,'Export private read report to folder')
        if directory:
            try: self.status.setText('Saved private report: '+str(export_capture(self.report,directory)))
            except (OSError,ValueError) as error: self.status.setText('Export failed: '+str(error))
