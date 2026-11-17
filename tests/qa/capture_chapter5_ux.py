"""chapter5-ux-001 수정 전후 화면·좌표 기록(실제 Tk 렌더링 캡처).

python tests/qa/capture_chapter5_ux.py <출력 폴더>

- 메모리 DB만 사용합니다. 사용자 저장은 열지 않고, 실행 전후 목록·SHA-256이 같지 않으면 실패로 기록합니다.
- 학습 단계 준비는 기존 테스트 도우미(엔진 직접 호출)를 사용합니다. 네이티브 마우스/키보드 플레이 실적이 아닙니다.
- 화면 판정용 조회(위젯 크기·문구·세션 상태)만 하며 게임 상태를 바꾸는 호출은 아래 '준비'와 '시점' 단계의 기존 GUI 메서드뿐입니다.
"""
import json
from pathlib import Path
import sys
import tkinter as tk

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from PIL import ImageGrab

from database import Database
from main import SimulatorApp
from tests.run_gui import preflight, saved_files
from tests.support import dismiss_story_popups
from tests.test_training import (SERVER, game_snapshot, pass_stage1, pass_stage2, pass_stage3, pass_stage4,
                                 regular_after_3b, stage5_evidence, to_training_incident)

SIZES = ('1060x700', '900x620', '1280x720', '1366x768')


def shot(window, path):
    window.lift(); window.update(); window.update_idletasks()
    x, y = window.winfo_rootx(), window.winfo_rooty()
    w, h = window.winfo_width(), window.winfo_height()
    image = ImageGrab.grab()
    scale = image.width/window.winfo_screenwidth()
    image.crop(tuple(round(v*scale) for v in (x, y, x+w, y+h))).save(path)
    return path.name


def labels(widget):
    out = []
    for child in widget.winfo_children():
        if isinstance(child, tk.Label) and child.cget('text'):
            out.append(child)
        out.extend(labels(child))
    return out


def header_metrics(lab):
    """헤더(Notebook 위)의 모든 문구가 창 안에 다 보이는지: 요청 폭 > 실제 폭이거나 오른쪽 끝이 창 밖이면 잘림."""
    lab.update_idletasks()
    header = lab.grid_slaves(row=0)[0]
    right = lab.winfo_rootx()+lab.winfo_width()
    rows = []
    for item in labels(header):
        if not item.winfo_ismapped():
            continue
        x = item.winfo_rootx()
        clipped = item.winfo_reqwidth() > item.winfo_width()+1 or x+item.winfo_width() > right+1
        rows.append({'text': item.cget('text'), 'req': item.winfo_reqwidth(), 'width': item.winfo_width(),
                     'height': item.winfo_height(), 'right': x+item.winfo_width()-lab.winfo_rootx(), 'clipped': clipped})
    button = lab.return_button
    bx = button.winfo_rootx()-lab.winfo_rootx()
    by = button.winfo_rooty()-lab.winfo_rooty()
    return {'window': [lab.winfo_width(), lab.winfo_height()], 'header_height': header.winfo_height(),
            'notebook_top': lab.book.winfo_rooty()-lab.winfo_rooty(),
            'labels': rows, 'clipped': [r['text'] for r in rows if r['clipped']],
            'return_button': {'x': bx, 'y': by, 'w': button.winfo_width(), 'h': button.winfo_height(),
                              'inside': bx >= 0 and by >= 0 and bx+button.winfo_width() <= lab.winfo_width()
                              and button.winfo_ismapped()},
            'training_bar_visible': bool(getattr(lab, 'training_bar', None) and lab.training_bar.winfo_ismapped()
                                         and lab.training_bar.winfo_rooty()+lab.training_bar.winfo_height()
                                         <= lab.winfo_rooty()+lab.winfo_height()+1)}


def run_state(session):
    run = session.runs[session.training.rid]
    s = run.state
    return {'minute': session.minute, 'phase': s.phase, 'progress': round(s.progress, 1), 'succeeded': s.succeeded,
            'recovered_by': s.recovered_by, 'recovery_left': s.recovery_left, 'score': s.score,
            'gpu_used': session.center.gpu_used, 'power_used': session.center.power_used,
            'allocated_ledger': run.playthrough_id in session.servers.allocations,
            'request_status': run.request['status'], 'training_done': session.training.done,
            'completed': list(session.training.completed)}


class Capture:
    def __init__(self, out, kind):
        self.out, self.kind = out, kind
        self.root = tk.Tk()
        self.root.geometry('1280x800+0+0')
        self.db = Database(':memory:')
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(repr(args[1]))
        if kind == 'regular':
            regular_after_3b(self.db).save()
            self.app = SimulatorApp(self.root, self.db, mode='story')
            self.root.update()
            self.app.begin_training()
        elif kind == 'preview':
            self.app = SimulatorApp(self.root, self.db, mode='story', start_chapter=3, seed=5)
        else:
            self.app = SimulatorApp(self.root, self.db, mode='story', start_chapter='lab', seed=5)
        self.root.update()
        dismiss_story_popups(self.app, self.root)
        self.data = {'kind': kind, 'header': {}, 'points': [], 'errors': self.errors}

    def close(self):
        try:
            self.app.network.stop()
        finally:
            self.root.destroy()
            self.db.close()

    def lab(self):
        lab = self.app.open_engineering_lab()
        self.root.update()
        return lab

    def headers(self):
        lab = self.lab()
        for size in SIZES:
            for tab in (('연수 진행', '가상 터미널') if '연수 진행' in lab.tabs else ('운영 상태',)):
                lab.geometry(size+'+10+10')  # 캡처가 화면 밖으로 잘리지 않게 위치 고정
                lab.show_tab(tab)
                lab.update(); lab.update_idletasks(); lab.update()
                tag = {'연수 진행': 'training', '가상 터미널': 'terminal'}.get(tab, 'operations')
                name = f'{self.kind}_header_{size}_{tag}.png'
                metrics = header_metrics(lab)
                metrics['shot'] = shot(lab, self.out/name)
                self.data['header'][f'{size}/{tab}'] = metrics
        lab.geometry('1060x700'); lab.update()

    def preview(self):
        """Chapter 3a 미션 A 관찰 미리보기(같은 헤더). 장애 상태에서 헤더만 기록합니다."""
        from tests.test_chapter3 import to_incident
        s = self.app.session
        s.confirm_chapter3_briefing()
        a = s.story.chapter3.request_ids[0]
        s.read_conversation(a); s.selected_id = a; s.choose_plan('performance')
        to_incident(s, a)
        self.app.refresh(); dismiss_story_popups(self.app, self.root)
        self.headers()

    def point(self, key, reopen=True):
        """현재 시점: Lab 목표 카드·결과창(열려 있으면 그대로, 그리고 닫았다 다시 연 화면)을 기록합니다."""
        app, session = self.app, self.app.session
        dismiss_story_popups(app, self.root)
        before = game_snapshot(session)
        lab = self.lab()
        lab.geometry('1060x700'); lab.show_tab('연수 진행'); lab.update()
        item = {'key': key, 'state': run_state(session),
                'lab': {'goal_chip': lab.goal_chip.cget('text') if hasattr(lab.goal_chip, 'cget') else None,
                        'goal_title': lab.goal_title.cget('text'), 'goal_detail': lab.goal_detail.cget('text'),
                        'shot': shot(lab, self.out/f'{self.kind}_{key}_lab.png')},
                'objective': session.story_objective()}
        window = app.chapter_window
        if session.training.done:
            if window is not None and window.winfo_exists() and type(window).__name__ == 'TrainingResultDialog':
                item['result_live'] = {'texts': [w.cget('text') for w in labels(window)],
                                       'shot': shot(window, self.out/f'{self.kind}_{key}_result_live.png')}
            if reopen:
                if window is not None and window.winfo_exists():
                    window.destroy()
                app.chapter_window = None
                window = app.show_training_result()
                self.root.update()
                item['result_reopened'] = {'texts': [w.cget('text') for w in labels(window)],
                                           'shot': shot(window, self.out/f'{self.kind}_{key}_result_reopened.png')}
        item['state_unchanged_by_viewing'] = game_snapshot(session) == before
        self.data['points'].append(item)
        return item

    def play(self):
        app, s = self.app, self.app.session
        rid = to_training_incident(s)
        app.refresh(); dismiss_story_popups(app, self.root)
        self.headers()
        for index, step in enumerate((pass_stage1, pass_stage2, pass_stage3, pass_stage4)):
            if s.training.practice:
                s.focus_training_stage(('structure', 'tool', 'assemble', 'terminal')[index])
            step(s)
            if not s.training.practice:
                s.start_next_stage()
        if s.training.practice:
            s.focus_training_stage('independent')
        app.refresh(); dismiss_story_popups(app, self.root)
        stage5_evidence(s)
        lab = self.lab()
        lab._answer('independent', 'cause', 'path_down')
        self.point('1_stage5_pending')
        app.select_request(rid)
        app.respond('reroute')
        self.root.update()
        self.point('2_after_reroute')
        lab = self.lab()
        lab.run_terminal(f'ping -c 3 {SERVER}')
        self.root.update()
        self.data['result_opened_automatically'] = (app.chapter_window is not None and app.chapter_window.winfo_exists()
                                                    and type(app.chapter_window).__name__ == 'TrainingResultDialog')
        self.point('3_stage5_passed', reopen=False)
        self.point('3b_stage5_passed_reopened')
        app.advance_time(10)
        self.root.update()
        self.point('4_recovery_done_running')
        for _ in range(30):
            if s.runs[rid].state.phase == 'finished':
                break
            app.advance_time(10)
            self.root.update(); dismiss_story_popups(app, self.root)
        self.point('5_job_finished')
        self.headers_after = None


def main():
    out = Path(sys.argv[1])
    (out/'shots').mkdir(parents=True, exist_ok=False)
    before = saved_files()
    report = {'environment': preflight(), 'runs': []}
    for kind in ('regular', 'practice', 'preview'):
        cap = Capture(out/'shots', kind)
        try:
            cap.preview() if kind == 'preview' else cap.play()
        except Exception as exc:  # 실패도 기록합니다.
            import traceback
            cap.data['exception'] = traceback.format_exc()
            print(traceback.format_exc())
        finally:
            report['runs'].append(cap.data)
            cap.close()
    after = saved_files()
    report['user_data_unchanged'] = before == after
    (out/'capture.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for run in report['runs']:
        clipped = {k: v['clipped'] for k, v in run['header'].items() if v['clipped']}
        print(run['kind'], 'clipped:', json.dumps(clipped, ensure_ascii=False))
        for p in run['points']:
            print(' ', p['key'], p['state']['phase'], p['state']['progress'], 'done' if p['state']['training_done'] else '',
                  'unchanged' if p['state_unchanged_by_viewing'] else 'CHANGED')
        print('  errors', run['errors'], run.get('exception', '')[:200])
    print('user data unchanged', report['user_data_unchanged'])


if __name__ == '__main__':
    main()
