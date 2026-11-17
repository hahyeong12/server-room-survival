"""ui-polish-001 게이지 글자 경계 측정·캡처(실제 Tk 렌더링, 메모리 DB).

python tests/qa/capture_gauges.py <출력 폴더>

Engineering Lab의 모든 Gauge(연수 진행률·운영 상태·서버 내부)에서 제목/수치/보조 문구/막대의 Canvas 경계를 읽어
서로 겹치거나 Canvas 밖으로 나가는지 기록합니다. 단계 준비는 기존 테스트 도우미(엔진 직접 호출)이며 네이티브 입력 실적이 아닙니다.
"""
import json
from pathlib import Path
import sys
import tkinter as tk

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from PIL import ImageGrab

from aidc.ui.ui_kit import Gauge
from database import Database
from main import SimulatorApp
from tests.run_gui import preflight, saved_files
from tests.support import dismiss_story_popups
from tests.test_training import (pass_stage1, pass_stage2, pass_stage3, pass_stage4, regular_after_3b,
                                 to_training_incident, finish_stage5)

SIZES = ('900x620', '1060x700', '1280x720', '1366x768')
PARTS = ('title', 'value', 'caption', 'track')


def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def gauge_metrics(gauge):
    gauge.update_idletasks()
    boxes = {}
    for tag in PARTS:
        items = gauge.find_withtag(tag)
        if items:
            boxes[tag] = list(gauge.bbox(*items))
    w, h = gauge.winfo_width(), gauge.winfo_height()
    pairs = [f'{a}/{b}' for i, a in enumerate(PARTS) for b in PARTS[i+1:]
             if a in boxes and b in boxes and overlap(boxes[a], boxes[b])]
    outside = [t for t, b in boxes.items() if b[0] < 0 or b[1] < 0 or b[2] > w+1 or b[3] > h+1]
    texts = {t: gauge.itemcget(gauge.find_withtag(t)[0], 'text') for t in ('title', 'value', 'caption') if t in boxes}
    return {'size': [w, h], 'boxes': boxes, 'texts': texts, 'overlaps': pairs, 'outside': outside}


def gauges(widget):
    found = []
    for child in widget.winfo_children():
        if isinstance(child, Gauge):
            found.append(child)
        found.extend(gauges(child))
    return found


def shot(widget, path):
    widget.update(); widget.update_idletasks()
    x, y, w, h = widget.winfo_rootx(), widget.winfo_rooty(), widget.winfo_width(), widget.winfo_height()
    image = ImageGrab.grab()
    scale = image.width/widget.winfo_screenwidth()
    image.crop(tuple(round(v*scale) for v in (x, y, x+w, y+h))).save(path)
    return path.name


def main():
    out = Path(sys.argv[1])
    (out/'shots').mkdir(parents=True, exist_ok=False)
    before = saved_files()
    report = {'environment': preflight(), 'cases': []}
    for kind in ('regular', 'practice'):
        root = tk.Tk(); root.geometry('1280x800+0+0')
        db = Database(':memory:')
        errors = []
        root.report_callback_exception = lambda *a: errors.append(repr(a[1]))
        try:
            if kind == 'regular':
                regular_after_3b(db).save()
                app = SimulatorApp(root, db, mode='story'); root.update(); app.begin_training()
            else:
                app = SimulatorApp(root, db, mode='story', start_chapter='lab', seed=5)
            root.update(); dismiss_story_popups(app, root)
            s = app.session
            to_training_incident(s)
            steps = (pass_stage1, pass_stage2, pass_stage3, pass_stage4)
            for count in (0, 3, 5):
                while s.training.completed_count < count and s.training.completed_count < 4:
                    index = s.training.completed_count
                    if s.training.practice:
                        s.focus_training_stage(('structure', 'tool', 'assemble', 'terminal')[index])
                    steps[index](s)
                    if not s.training.practice:
                        s.start_next_stage()
                if count == 5:
                    if s.training.practice:
                        s.focus_training_stage('independent')
                    finish_stage5(s)
                app.refresh(); dismiss_story_popups(app, root)
                window = app.chapter_window
                if window is not None and window.winfo_exists() and type(window).__name__ == 'TrainingResultDialog':
                    window.destroy(); app.chapter_window = None
                lab = app.open_engineering_lab(); root.update()
                for size in SIZES:
                    for tab in ('연수 진행', '운영 상태', '서버 내부'):
                        lab.geometry(size+'+10+10'); lab.show_tab(tab)
                        lab.update(); lab.update_idletasks(); lab.update()
                        found = [g for g in gauges(lab.tabs[tab]) if g.winfo_ismapped()]
                        case = {'kind': kind, 'count': s.training.completed_count, 'size': size, 'tab': tab,
                                'gauges': [gauge_metrics(g) for g in found]}
                        if tab == '연수 진행':
                            case['goal_card_height'] = lab.goal_card.winfo_height()
                            case['task_area_height'] = lab.training_area.winfo_height()
                            if size in ('900x620', '1060x700'):
                                case['shot'] = shot(lab.goal_card, out/'shots'/f'{kind}_{case["count"]}of5_{size}_card.png')
                        elif size == '1060x700' and case['count'] == 0:
                            case['shot'] = shot(lab.tabs[tab], out/'shots'/f'{kind}_{size}_{"ops" if tab == "운영 상태" else "servers"}.png')
                        report['cases'].append(case)
        finally:
            report.setdefault('errors', {})[kind] = errors
            app.network.stop(); root.destroy(); db.close()
    report['user_data_unchanged'] = saved_files() == before
    (out/'gauges.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    bad = [(c['kind'], c['count'], c['size'], c['tab'], g['texts'].get('title'), g['overlaps'], g['outside'])
           for c in report['cases'] for g in c['gauges'] if g['overlaps'] or g['outside']]
    print('cases', len(report['cases']), 'problems', len(bad))
    for item in bad[:40]:
        print(' ', item)
    print('card/task heights', sorted({(c['size'], c['goal_card_height'], c['task_area_height'])
                                       for c in report['cases'] if c['tab'] == '연수 진행'}))
    print('errors', report['errors'], 'user data unchanged', report['user_data_unchanged'])


if __name__ == '__main__':
    main()
