"""Read-only integration probe. Run with --hardware to access COM18."""
import sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication,QTimer
from backend import Session,resolve_client

app = QCoreApplication(sys.argv)
session = Session()
hardware = '--hardware' in sys.argv
queue = ['hw version','hw status','hw ping'] if hardware else ['prefs show','hw version']
if '--identify' in sys.argv and hardware: queue += ['lf search','hf search']
expected_count = len(queue)
results = []
session.output.connect(lambda text: print(text,end='',flush=True))
def state(text):
    print('\nSTATE:',text,flush=True)
    if text == 'Ready': QTimer.singleShot(10,next_command)
def next_command():
    if queue:
        session.send(queue.pop(0))
    else:
        session.stopping = True; session.process.kill(); session.process.waitForFinished(2000); app.quit()
def completed(command,text):
    results.append(command)
    print('\nCOMPLETED:',command,flush=True)
def fail(text):
    print('\nFAILED:',text,flush=True); app.exit(1)
session.state.connect(state); session.completed.connect(completed); session.failed.connect(fail)
session.start(resolve_client(r'C:\rrg_other\pm3.bat'),'COM18',Path(__file__).parent,offline=not hardware)
QTimer.singleShot(90000,lambda: fail('Integration probe timeout'))
code = app.exec()
session.process.kill(); session.process.waitForFinished(2000)
print('TRANSACTIONS:',results)
sys.exit(code if len(results) == expected_count else 1)
