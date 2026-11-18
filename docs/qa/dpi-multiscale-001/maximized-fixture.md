# 최대화 준비 조건 재현 기록

150% 기본 창의 Preflight 실패를 보존한 뒤 실행한 **별도 추가 검사**입니다. 기존 검사와 게임 코드는 수정하지 않았습니다. 실행 도구는 로컬 `artifacts/dpi-multiscale-001/run_maximized.py`에 보존하며, 문서 전용 커밋에는 아래 재현 기록만 포함합니다.

사용자가 실제 Windows 배율을 변경하고 DPI를 확인한 뒤 저장소 루트에서 실행합니다. 이 코드를 `artifacts/dpi-multiscale-001/run_maximized.py`로 저장하면 아래 경로 계산과 맞습니다. 전경을 사용하는 실제 입력 검사는 동시에 실행하지 않습니다.

```powershell
& 'C:\anaconda3\python.exe' artifacts/dpi-multiscale-001/run_maximized.py tests/qa/autoplay_chapter5.py --focus <새-집중검사-폴더>
& 'C:\anaconda3\python.exe' artifacts/dpi-multiscale-001/run_maximized.py tests/qa/autoplay_chapter5.py <새-정규플레이-폴더> <집중검사-폴더>/result.json
```

준비 단계에서 창을 최대화하며, 원본 Preflight·입력 소유 확인·게임 조작·판정은 그대로입니다. 이미 최대화한 창에 대한 중복 최대화 요청만 멱등 처리합니다. 기본 창 실패와 최대화 추가 결과를 합쳐 전체 PASS로 표시하지 않습니다. Windows 배율·레지스트리·게임 설정·저장을 변경하는 도구가 아닙니다.

```python
"""Supplemental native QA: start maximized, preserve all guards and assertions.

The original default-window failure remains a separate result. Only fixture
window state changes; a repeated maximize request is idempotent.
"""
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'tests/qa')]
from aidc.ui import dpi
assert dpi.enable_system_awareness(), dpi.status()
from autoplay_story_ch1 import StoryHarness
from gui_driver import Harness

original_preflight = StoryHarness.preflight
original_maximize = Harness.maximize_root

def preflight(self):
    self.call(lambda: (self.root.state('zoomed'), self.root.update()))
    self.note('Supplemental fixture: maximized before original preflight; guards unchanged')
    return original_preflight(self)

def maximize(self):
    if self.call(lambda: self.root.state()) == 'zoomed':
        return 'zoomed'
    return original_maximize(self)

StoryHarness.preflight = preflight
Harness.maximize_root = maximize
target = Path(sys.argv[1]).resolve()
print('[maximized fixture]', json.dumps(dpi.status()), flush=True)
sys.argv = [str(target), *sys.argv[2:]]
runpy.run_path(str(target), run_name='__main__')
```
