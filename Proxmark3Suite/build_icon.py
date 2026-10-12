"""Render the original vector icon into PNG and a multi-resolution Windows ICO."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import struct
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

def build():
    app = QGuiApplication.instance() or QGuiApplication([])
    assets = Path(__file__).resolve().parent / 'assets'
    renderer = QSvgRenderer(str(assets / 'app-icon.svg'))
    if not renderer.isValid():
        raise ValueError('Invalid icon SVG')
    images = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        canvas = QImage(size, size, QImage.Format_ARGB32)
        canvas.fill(Qt.transparent)
        painter = QPainter(canvas)
        renderer.render(painter)
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        if not canvas.save(buffer, 'PNG'):
            raise RuntimeError('PNG encoder unavailable')
        images.append((size, bytes(data)))
        if size == 256:
            canvas.save(str(assets / 'app-icon.png'))
    offset = 6 + 16 * len(images)
    entries = []
    for size, payload in images:
        entries.append(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(payload), offset))
        offset += len(payload)
    (assets / 'app-icon.ico').write_bytes(struct.pack('<HHH', 0, 1, len(images)) + b''.join(entries) + b''.join(payload for _, payload in images))

if __name__ == '__main__':
    build()
