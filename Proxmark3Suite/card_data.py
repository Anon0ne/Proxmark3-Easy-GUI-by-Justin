"""Local Classic dump drafts. No device commands or physical writes."""
from pathlib import Path
import hashlib
import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTreeWidget,
    QTreeWidgetItem,QPlainTextEdit,QLineEdit,QFileDialog,QMessageBox,QSplitter,QHeaderView,QTabWidget)
from emulation import inspect_dump,SIZES

# NXP MF1S50YYX_V1 Rev 3.2, Tables 7 and 8. Entries indexed by C1 C2 C3.
# https://www.nxp.com/docs/en/data-sheet/MF1S50YYX_V1.pdf
DATA_PERMISSIONS = {
    0:('A/B','A/B','A/B','A/B'),1:('A/B','Never','Never','A/B'),
    2:('A/B','Never','Never','Never'),3:('B','B','Never','Never'),
    4:('A/B','B','Never','Never'),5:('B','Never','Never','Never'),
    6:('A/B','B','B','A/B'),7:('Never','Never','Never','Never')}
TRAILER_PERMISSIONS = {
    0:('A','A','Never','A','A'),1:('A','A','A','A','A'),
    2:('Never','A','Never','A','Never'),3:('B','A/B','B','Never','B'),
    4:('B','A/B','Never','Never','B'),5:('Never','A/B','B','Never','Never'),
    6:('Never','A/B','Never','Never','Never'),7:('Never','A/B','Never','Never','Never')}

def block_location(block,count):
    if not 0 <= block < count: raise ValueError('Block is outside the dump.')
    if block < 128: return block//4,block%4,block//4*4+3
    return 32+(block-128)//16,(block-128)%16,128+(block-128)//16*16+15

def access_codes(trailer):
    if len(trailer) != 16: raise ValueError('Trailer must be 16 bytes.')
    a,b,c = trailer[6:9]
    if ((a&15)^(b>>4)) != 15 or ((a>>4)^(c&15)) != 15 or ((b&15)^(c>>4)) != 15:
        raise ValueError('Invalid access-bit complements: permissions cannot be decoded reliably.')
    return [(((b>>(4+i))&1)<<2)|(((c>>i)&1)<<1)|((c>>(4+i))&1) for i in range(4)]

def describe_permissions(data,block):
    sector,relative,trailer = block_location(block,len(data)//16)
    codes = access_codes(data[trailer*16:trailer*16+16])
    group = 3 if block == trailer else relative if block < 128 else relative//5
    code = codes[group]
    text = f'Sector {sector}, block {block}\nAccess code C1 C2 C3: {code:03b}\n'
    if block == trailer:
        text += 'Key A read: Never\n' + '\n'.join(f'{label}: {value}' for label,value in zip(
            ('Key A write','Access bits read','Access bits write','Key B read','Key B write'),TRAILER_PERMISSIONS[code]))
    else:
        permissions = DATA_PERMISSIONS[code]
        # A readable Key B is data, not an authentication key in this sector.
        if codes[3] in (0,1,2):
            permissions = tuple('A' if p == 'A/B' else 'Never' if p == 'B' else p for p in permissions)
        if block == 0: permissions = (permissions[0],'Never','Never','Never')
        text += '\n'.join(f'{label}: {value}' for label,value in zip(
            ('Read','Write','Increment','Decrement / transfer / restore'),permissions))
    if codes[3] in (0,1,2): text += '\nKey B is readable and cannot authenticate this sector.'
    if block == 0: text += '\nManufacturer block: standard cards are read-only. Magic-card behavior is generation-specific.'
    return text+'\nPermissions describe encoded conditions, not proof that keys are known.'

class DumpDraft:
    def __init__(self,path):
        self.source = Path(path).resolve()
        self.original,self.metadata = inspect_dump(self.source)
        self.data = bytearray(self.original); self.history = []

    def edit(self,block,value):
        block_location(block,len(self.data)//16)
        compact = re.sub(r'\s','',value)
        if not re.fullmatch('[0-9a-fA-F]{32}',compact): raise ValueError('Enter exactly 16 bytes: 32 hexadecimal characters.')
        previous = bytes(self.data[block*16:block*16+16]); replacement = bytes.fromhex(compact)
        if replacement != previous:
            self.history.append((block,previous)); self.data[block*16:block*16+16] = replacement

    def undo(self):
        if self.history:
            block,previous = self.history.pop(); self.data[block*16:block*16+16] = previous

    def changed(self):
        return [i for i in range(len(self.data)//16) if self.data[i*16:i*16+16] != self.original[i*16:i*16+16]]

    def export(self,path):
        target = Path(path).resolve()
        if target == self.source or target.exists() and target.samefile(self.source):
            raise ValueError('Choose a new file. The original dump is preserved.')
        if target.suffix.lower() not in ('.bin','.eml'): raise ValueError('Export a BIN or EML file.')
        # Atomic replacement prevents a failed write from truncating another draft.
        import uuid
        temp = target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
        try:
            payload = bytes(self.data) if target.suffix.lower()=='.bin' else ('\n'.join(bytes(self.data[i:i+16]).hex().upper() for i in range(0,len(self.data),16))+'\n').encode('ascii')
            temp.write_bytes(payload); temp.replace(target)
        finally:
            if temp.exists(): temp.unlink()

class CardDataPanel(QWidget):
    def __init__(self,owner):
        super().__init__(); self.owner = owner; self.draft = None; self.comparison = None
        outer = QVBoxLayout(self); pages = QTabWidget(); outer.addWidget(pages)
        editor = QWidget(); pages.addTab(editor,'Local dump editor'); layout = QVBoxLayout(editor)
        from card_reads import CardReadPanel
        self.reads = CardReadPanel(owner); pages.addTab(self.reads,'Read from card')
        self.recovery_results = QPlainTextEdit(); self.recovery_results.setReadOnly(True)
        self.recovery_results.setPlaceholderText('After a Classic recovery command, every sector and the keys explicitly reported by the client appear here. Unknown keys remain unknown.'); pages.addTab(self.recovery_results,'Recovery results')
        note = QLabel('Inspect and edit a local Classic dump. Edits stay in a draft until exported; original files are preserved. No device or card writes are performed here.')
        note.setWordWrap(True); layout.addWidget(note)
        actions = QHBoxLayout(); layout.addLayout(actions)
        for label,callback in [('Open dump…',self.open_dump),('Compare dump…',self.compare),('Undo',self.undo),('Export draft…',self.export)]:
            button = QPushButton(label); button.clicked.connect(callback); actions.addWidget(button)
        self.summary = QLabel('Open a BIN, DUMP, EML or Iceman Classic JSON file, or inspect a saved Emulation slot.'); self.summary.setWordWrap(True); layout.addWidget(self.summary)
        splitter = QSplitter(); layout.addWidget(splitter,1)
        self.table = QTreeWidget(); self.table.setHeaderLabels(['Sector','Block','Kind','Draft hex','State'])
        self.table.header().setSectionResizeMode(3,QHeaderView.Stretch); self.table.setFont(QFont('Consolas',10)); splitter.addWidget(self.table)
        for column in (0,1,2,4): self.table.header().setSectionResizeMode(column,QHeaderView.ResizeToContents)
        side = QWidget(); form = QVBoxLayout(side); splitter.addWidget(side); splitter.setStretchFactor(0,3); splitter.setStretchFactor(1,2)
        self.permissions = QPlainTextEdit(); self.permissions.setReadOnly(True); form.addWidget(self.permissions,1)
        form.addWidget(QLabel('Selected block draft — 16 hexadecimal bytes'))
        self.hex = QLineEdit(); self.hex.setMaxLength(100); form.addWidget(self.hex)
        apply = QPushButton('Apply to local draft'); apply.clicked.connect(self.apply); form.addWidget(apply)
        self.original = QLabel(''); self.original.setWordWrap(True); form.addWidget(self.original)
        self.table.currentItemChanged.connect(self.selection)

    def discard_allowed(self):
        return not self.draft or not self.draft.changed() or QMessageBox.question(self,'Discard local edits?','The current draft has unsaved changes. Export it first if you want to keep them. Discard changes?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes

    def load_path(self,path):
        if not self.discard_allowed(): return False
        try: draft = DumpDraft(path)
        except (OSError,ValueError) as error: self.error(error); return False
        self.draft = draft; self.comparison = None; self.refresh(); return True

    def open_dump(self):
        path,_ = QFileDialog.getOpenFileName(self,'Open Classic dump','','Classic dumps (*.bin *.dump *.eml *.json)')
        if path: self.load_path(path)

    def error(self,error): QMessageBox.warning(self,'Card data',str(error))

    def refresh(self,selected=0):
        self.table.clear()
        if not self.draft: return
        changed = set(self.draft.changed()); differences = 0
        for block in range(len(self.draft.data)//16):
            sector,_,trailer = block_location(block,len(self.draft.data)//16)
            payload = bytes(self.draft.data[block*16:block*16+16])
            differs = self.comparison is not None and payload != self.comparison[block*16:block*16+16]
            differences += differs
            state = ('Edited' if block in changed else 'Original')+(' · differs' if differs else '')
            item = QTreeWidgetItem([str(sector),str(block),'Manufacturer' if block==0 else 'Trailer' if block==trailer else 'Data',payload.hex().upper(),state])
            item.setToolTip(3,payload.hex(' ').upper())
            item.setData(0,Qt.UserRole,block); self.table.addTopLevelItem(item)
            if block in changed or differs: item.setForeground(4,QColor('#17bda9'))
            if block==selected: self.table.setCurrentItem(item)
        self.summary.setText(f'{self.draft.source.name} · Classic {self.draft.metadata["size"].upper()} · {len(changed)} edited blocks'+(f' · {differences} blocks differ from comparison' if self.comparison is not None else '')+'\nOriginal SHA256: '+self.draft.metadata['sha256']+'\nDraft SHA256: '+hashlib.sha256(self.draft.data).hexdigest())

    def selection(self,*_):
        item = self.table.currentItem()
        if not item or not self.draft: return
        block = item.data(0,Qt.UserRole)
        self.hex.setText(bytes(self.draft.data[block*16:block*16+16]).hex().upper())
        self.original.setText('Original: '+self.draft.original[block*16:block*16+16].hex(' ').upper())
        try: text = describe_permissions(self.draft.data,block)
        except ValueError as error: text = str(error)
        self.permissions.setPlainText(text)

    def apply(self):
        item = self.table.currentItem()
        if not item or not self.draft: return
        block = item.data(0,Qt.UserRole)
        if block==0 or block==block_location(block,len(self.draft.data)//16)[2]:
            if QMessageBox.question(self,'Edit sensitive block in draft?','This block contains identity or keys/access conditions. Editing the local file does not change the card. Apply to draft?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes: return
        try: self.draft.edit(block,self.hex.text()); self.refresh(block)
        except ValueError as error: self.error(error)

    def undo(self):
        if self.draft: self.draft.undo(); self.refresh()

    def compare(self):
        if not self.draft: return
        path,_ = QFileDialog.getOpenFileName(self,'Compare Classic dump','','Classic dumps (*.bin *.dump *.eml *.json)')
        if not path: return
        try:
            data,_ = inspect_dump(path)
            if len(data)!=len(self.draft.data): raise ValueError('Comparison dump must have the same card size.')
            self.comparison = data; self.refresh()
        except (OSError,ValueError) as error: self.error(error)

    def export(self):
        if not self.draft: return
        path,_ = QFileDialog.getSaveFileName(self,'Export local draft',str(self.draft.source.with_name(self.draft.source.stem+'-draft.bin')),'Binary (*.bin);;Text blocks (*.eml)')
        if path:
            try:
                self.draft.export(path)
                self.summary.setText('Exported local draft: '+path+'\nOriginal preserved. Reopen the exported file to begin a new draft.')
            except (OSError,ValueError) as error: self.error(error)
