"""Conservative detection and firmware-derived MIFARE Classic recovery plans."""
from dataclasses import dataclass
import re
from catalog import clean

@dataclass(frozen=True)
class ClassicCard:
    uid: str
    size: str

def card_uid(text):
    values = set()
    for match in re.finditer(r'(?im)\bUID:[ \t]*([0-9a-f]{2}(?:[ :]*[0-9a-f]{2}){3,9})[ \t]*(?:\([^\r\n]*\))?[ \t]*$',clean(text)):
        uid = re.sub(r'[^0-9a-f]','',match.group(1),flags=re.I).upper()
        if len(uid) in {8,14,20}: values.add(uid)
    return next(iter(values)) if len(values) == 1 else None

def detect_classic(text):
    text = clean(text)
    if re.search(r'No known/supported|not found|no tag|DESFire|Ultralight|NTAG|MIFARE Plus',text,re.I): return None
    uid = card_uid(text)
    sizes = set(re.findall(r'(?i)MIFARE Classic\s+(Mini|1K|2K|4K)\b',text))
    sizes = {size.lower() for size in sizes}
    if re.search(r'(?i)MIFARE Mini\s+0\.3K\b',text): sizes.add('mini')
    if not uid or len(sizes) != 1: return None
    return ClassicCard(uid,next(iter(sizes)))

def recovery_command(card,commands):
    meta = commands.get('hf mf autopwn')
    if not meta or 'hf 14a reader' not in commands:
        raise ValueError('The installed client lacks the documented recovery/UID verification commands.')
    flags = {option.flag for option in meta.options}
    size_flag = '--'+card.size
    if size_flag not in flags or '--file' not in flags:
        raise ValueError('The installed client does not document the required size/dictionary options.')
    # This exact default dictionary is an installed-client help example.
    if 'mfc_default_keys' not in meta.help:
        raise ValueError('Default dictionary is not documented by the selected client; use the workbench manually.')
    return 'hf mf autopwn '+size_flag+' --file mfc_default_keys'

def recovery_sectors(text,size):
    """Last firmware key table, retaining unknown sectors and result markers."""
    count={'mini':5,'1k':16,'2k':32,'4k':40}.get(size)
    if count is None: raise ValueError('Unsupported Classic size.')
    rows={}; table=False
    for raw in clean(text).splitlines():
        line=re.sub(r'^\s*\[[^]]+\]\s*','',raw)
        if re.search(r'Sec\s*\|\s*Blk\s*\|\s*key A\s*\|res\|\s*key B',line,re.I): rows={}; table=True; continue
        if not table: continue
        match=re.match(r'^\s*\|?\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([0-9a-fA-F]{12}|-{12})\s*\|\s*([^|]*)\|\s*([0-9a-fA-F]{12}|-{12})\s*\|\s*([^|\r\n]*?)(?:\s*\||\s*$)',line)
        if not match or not 0<=int(match[1])<count: continue
        row={}
        for label,key,marker in [('A',match[3],match[4]),('B',match[5],match[6])]:
            marker=marker.strip()
            known=bool(re.fullmatch('[0-9a-fA-F]{12}',key) and re.fullmatch('[1-9A-Za-z]',marker))
            row[label]={'status':'reported found' if known else 'unknown','key':key.upper() if known else None,'marker':marker}
        rows[int(match[1])]=row
    return [{'sector':sector,**rows.get(sector,{label:{'status':'unknown','key':None,'marker':None} for label in ('A','B')})} for sector in range(count)]

def card_summary(uid, observations):
    """Only explicitly reported card facts; never command chatter or guesses."""
    facts = {}
    types = set()
    for text in observations.values():
        for raw in clean(text).splitlines():
            line = re.sub(r'^\s*\[[^\]]\]\s*', '', raw).strip()
            for label, pattern in [
                ('ATQA', r'^ATQA:\s*([0-9A-Fa-f ]+)'),
                ('SAK', r'^SAK:\s*([0-9A-Fa-f]{2})\b'),
                ('Magic capabilities', r'^Magic capabilities[. :]+(.+)'),
                ('Static nonce', r'^Static nonce[. :]+(.+)'),
                ('PRNG', r'^PRNG[. :]+(.+)'),
                ('Manufacturer block', r'^Block 0[. :]+([0-9A-Fa-f]{32})\b'),
            ]:
                match = re.search(pattern,line,re.I)
                if match:
                    key = label
                    value = match.group(1).strip()
                    if label == 'Static nonce' and re.fullmatch(r'[0-9a-f]{8}',value,re.I): key = 'Nonce value'
                    facts[key] = value
            match = re.match(r'^Sector\s+(\d+)\s+key\s+([AB])[. :]+([0-9a-f]{12})\b',line,re.I)
            if match: facts['Sector '+match[1]+' key '+match[2].upper()] = match[3].upper()
            if line.startswith(('MIFARE Classic','MIFARE Mini','MIFARE DESFire','NTAG','MIFARE Ultralight')):
                types.add(line)
            if re.fullmatch(r'(?:Fudan|NXP|Infineon)[\w /-]* (?:based card|card)',line,re.I): facts['Fingerprint'] = line
    result = ['UID: '+uid]
    if types: result.append('Reported type: '+', '.join(sorted(types)))
    result += [label+': '+value for label,value in facts.items()]
    return '\n'.join(result)
