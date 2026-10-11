"""Convert terminal redraw output into readable, line-oriented GUI output."""
import re
from catalog import ANSI

class EventLogFormatter:
    def __init__(self):
        self.pending = ''

    def feed(self, text):
        self.pending += text
        parts = re.split(r'[\r\n]+', self.pending)
        self.pending = parts.pop()
        output = []
        for part in parts:
            line = ANSI.sub('', part)
            # Spinner-only redraws add no information to an event log.
            line = re.sub(r'^\s*\[[/\\|\-]\]\s*(?=\[|Searching for |$)', '', line)
            if not line.strip() or re.search(r'(?:rem|remark:)\s+SUITE_[0-9a-f]+', line):
                continue
            output.append(line.rstrip() + '\n')
        return ''.join(output)
