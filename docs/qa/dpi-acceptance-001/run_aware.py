"""dpi-acceptance-001: 기존 네이티브 QA 스크립트를 수정 없이 System DPI Aware 프로세스에서 실행합니다.

python run_aware.py <QA 스크립트 경로> [그 스크립트의 인자...]

게임의 실험 플래그(SRS_DPI_AWARE=system)와 같은 aidc.ui.dpi.enable_system_awareness()를 Tk 창 생성 전에 호출합니다.
기존 하네스는 main()을 거치지 않고 Tk 루트를 직접 만들기 때문에 이 래퍼가 필요합니다. 설정에 실패하면 실행하지 않습니다.
"""
import json
import os
from pathlib import Path
import runpy
import sys

REPO = Path(os.environ.get('SRS_REPO', Path.cwd())).resolve()
sys.path.insert(0, str(REPO))
from aidc.ui import dpi

if not dpi.enable_system_awareness():
    raise SystemExit('System DPI Aware 설정 실패: ' + dpi.status()['reason'])
target = Path(sys.argv[1]).resolve()
print('[run_aware] dpi', json.dumps(dpi.status(), ensure_ascii=False), flush=True)
sys.argv = [str(target)] + sys.argv[2:]
runpy.run_path(str(target), run_name='__main__')
