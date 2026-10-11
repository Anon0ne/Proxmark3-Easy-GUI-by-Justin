"""Metadata from the installed client's --fulltext dump, never upstream guesses."""
from dataclasses import dataclass, field, asdict
import re

ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')

def clean(text):
    return re.sub(r'\r+(?:\n)?', '\n', ANSI.sub('', text))

@dataclass
class Option:
    flag: str
    value: str = ''
    description: str = ''
    choices: list = field(default_factory=list)

@dataclass
class Command:
    name: str
    offline: bool
    help: str
    options: list = field(default_factory=list)

def parse_dump(text):
    commands = {}
    for block in re.split(r'(?m)^-{20,}\s*$', clean(text)):
        match = re.match(r'\s*([\w -]+?)\s*\navailable offline: (yes|no)\s*\n(.*)', block, re.S)
        if not match:
            continue
        name, offline, help_text = match.groups()
        name = name.strip()
        options = []
        section = help_text.split('options:', 1)
        if len(section) == 2:
            for line in section[1].split('examples/notes:', 1)[0].splitlines():
                m = re.match(r'^\s+(-\S.*?)\s{2,}(.*)$', line)
                if not m:
                    continue
                syntax, description = m.groups()
                flags = re.findall(r'(?<!\w)--?[\w-]+', syntax)
                if not flags or '--help' in flags or flags == ['-h']:
                    continue
                flag = next((f for f in flags if f.startswith('--')), flags[0])
                value = re.search(r'(<[^>]+>|\[[^\]]+\])', syntax)
                placeholder = value.group(1) if value else ''
                # Only create choices explicitly enumerated in option syntax.
                choices = placeholder[1:-1].split('|') if '|' in placeholder else []
                options.append(Option(flag, placeholder, description, choices))
        commands[name] = Command(name, offline == 'yes', help_text.strip(), options)
    if not commands:
        raise ValueError('No firmware command metadata recognized in client dump')
    return commands

READ_ONLY = {'hw version', 'hw status', 'hw ping', 'hf search', 'lf search', 'hf 14a reader', 'hf mf info'}

def validate_line(line):
    # Current upstream pipe reader has a 256-byte line buffer. Reject truncation
    # that could turn a long argument into a second unintended command.
    if len(line.encode('utf-8')) > 250:
        raise ValueError('Command exceeds the client pipe reader limit of 250 bytes.')
    if not line.strip() or any(ord(c) < 32 for c in line) or ';' in line:
        raise ValueError('Enter one command only; command separators and control characters are prohibited.')

def needs_confirmation(line):
    # Fail closed: only exact reviewed commands and exact discovered help are exempt.
    validate_line(line)
    return line.strip() not in READ_ONLY

def build_command(name, values, extra=''):
    parts = [name]
    for option, value in values:
        if option.value:
            if value.strip():
                if any(c in value for c in '"\r\n;\x00'):
                    raise ValueError('Argument contains a quote or command separator.')
                parts.extend([option.flag, '"' + value.strip() + '"'])
        elif value:
            parts.append(option.flag)
    if extra.strip():
        parts.append(extra.strip())
    line = ' '.join(parts)
    validate_line(line)
    return line
