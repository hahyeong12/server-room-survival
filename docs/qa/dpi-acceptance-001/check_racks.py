"""dpi-acceptance-001: 서버실 랙 배치(큰 숫자형/한 줄 요약형 등)별 실제 마우스 선택·표시 검사.

python check_racks.py <새 출력 폴더>            # 현재 프로세스 DPI 상태(기본: 비인식)
python run_aware.py check_racks.py <새 출력 폴더> # 실험 System DPI Aware

- 기존 StoryHarness(Preflight·안전 클릭·가림 감시)를 그대로 씁니다. 저장은 하네스의 임시 폴더 슬롯만 사용합니다.
- 준비(판정 대상 아님): 새 연습 슬롯 생성(ModeSelection.new_story), 안내창 닫기(tests.support.dismiss_story_popups),
  창 크기 변경(root.geometry). 판정 대상인 랙 선택은 모두 Win32 실제 마우스 클릭입니다.
- 각 배치에서 확인: 랙 A~D 실제 클릭 → 선택·Inspector 서버 이름·선택 테두리 / 랙 글자가 랙 경계 안 /
  랙 안 글자끼리 겹침 수(두 모드 비교용).
"""
import json
import os
from pathlib import Path
import sys
import tempfile

REPO = Path(os.environ.get('SRS_REPO', Path.cwd())).resolve()
sys.path.insert(0, str(REPO / 'tests' / 'qa'))
sys.path.insert(0, str(REPO))
from autoplay_story_ch1 import StoryHarness, db_hashes
from gui_driver import AbortQA

SIZES = ('기본(작업 영역 맞춤)', '1280x680', '1000x650')


def overlap(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def scenario(h):
    from aidc.ui import dpi
    from server_console import rack_layout, CYAN
    from tests.support import dismiss_story_popups
    h.step = '준비'
    h.call(lambda: h.selector.new_story('lab'))
    app = lambda: h.selector.app
    h.call(lambda: dismiss_story_popups(app(), h.root))
    h.layouts = []
    for size in SIZES:
        h.step = f'랙 배치 {size}'
        if size in ('1280x680', '1000x650'):
            h.call(lambda: (h.root.state('normal'), h.root.geometry(dpi.geometry(size)), h.root.update()))
        h.call(lambda: (h.root.update(), h.root.update_idletasks()))

        def measure():
            net = app().network
            s = dpi.scale()
            columns = net.columns
            rows = 1 if columns == 4 else 2
            rack_h = (net.winfo_height()/s - 40 - 10*(rows-1)) / rows
            info = {'size': size, 'scale': s, 'canvas': [net.winfo_width(), net.winfo_height()], 'columns': columns,
                    'rack_height_design_px': round(rack_h, 1), 'layout': rack_layout(columns, rack_h),
                    'root': [h.root.winfo_width(), h.root.winfo_height()], 'racks': {}}
            for key, box in net.rack_bounds.items():
                texts = [(i, net.itemcget(i, 'text'), net.bbox(i)) for i in net.find_withtag('server-'+key)
                         if net.type(i) == 'text']
                outside = [t for _, t, b in texts if b[0] < box[0]-1 or b[1] < box[1]-1 or b[2] > box[2]+1 or b[3] > box[3]+1]
                pairs = [(a[1], b[1]) for n, a in enumerate(texts) for b in texts[n+1:]
                         if overlap(a[2], b[2]) > 4 and 'battery' not in ' '.join(net.gettags(a[0])+net.gettags(b[0]))]
                info['racks'][key] = {'bounds': [round(v, 1) for v in box], 'texts': [t for _, t, _ in texts],
                                      'outside': outside, 'text_overlaps': pairs,
                                      'origin': [net.winfo_rootx(), net.winfo_rooty()]}
            return info
        info = h.call(measure)
        h.note(f"배치 {size}: canvas {info['canvas']} columns {info['columns']} rack {info['rack_height_design_px']} → {info['layout']}")
        h.shot('racks_'+info['layout']+'_'+size.split('(')[0], note=f'{size} · {info["layout"]}')
        info['clicks'] = []
        for key in ('B', 'C', 'D', 'A'):
            rack = info['racks'][key]
            x0, y0, x1, y1 = rack['bounds']
            cx, cy = int(rack['origin'][0] + (x0+x1)/2), int(rack['origin'][1] + y0 + (y1-y0)*0.15)
            item = {'x': cx, 'y': cy, 'w': 0, 'h': 0, 'text': f'Server {key} 랙', 'class': 'Canvas', 'top': '.', 'inside_top': True}
            h.click(item, settle=.8)

            def after(key=key):
                net, panel = app().network, app().resources
                border = [i for i in net.find_withtag('server-'+key) if 'rack-border' in net.gettags(i)]
                inspector = panel.inspector
                name = inspector.values['spec'].name if getattr(inspector, 'values', None) else None
                return {'key': key, 'network_selected': net.selected, 'panel_selected': panel.selected,
                        'inspector_name': name, 'border_outline': net.itemcget(border[0], 'outline') if border else None}
            result = h.call(after)
            ok = (result['network_selected'] == key and result['panel_selected'] == key
                  and result['inspector_name'] == f'Server {key}' and result['border_outline'] == CYAN)
            h.check(h.step, f'Server {key} 실제 클릭 → 선택·Inspector·테두리', ok, result)
            info['clicks'].append(result | {'ok': ok, 'point': [cx, cy]})
        outside = {k: v['outside'] for k, v in info['racks'].items() if v['outside']}
        h.check(h.step, '랙 글자가 랙 경계 안', not outside, outside)
        info['overlap_count'] = sum(len(v['text_overlaps']) for v in info['racks'].values())
        h.note(f"랙 안 글자 겹침 {info['overlap_count']}쌍 {[v['text_overlaps'] for v in info['racks'].values()][:1]}")
        h.layouts.append(info)
    h.completed = True


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=False)
    before = db_hashes()
    h = StoryHarness(out)
    error = None
    try:
        error = h.run(scenario)['error']
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
    after = db_hashes()
    h.check('보존', '사용자 저장·잠금 보존', before == after, f'{len(before)}→{len(after)}개')
    from aidc.ui import dpi
    completed = getattr(h, 'completed', False)
    removed = h.cleanup() if completed and not error and not any(c['result'] == 'FAIL' for c in h.checks) else []
    assert h.tmp.resolve().parent == Path(tempfile.gettempdir()).resolve()
    report = {'kind': 'dpi_acceptance_rack_check', 'dpi': dpi.status(), 'completed': completed, 'error': error,
              'passed': sum(c['result'] == 'PASS' for c in h.checks), 'failed': sum(c['result'] == 'FAIL' for c in h.checks),
              'clicks': h.clicks, 'preflight': h.preflight_data.get('status'), 'layouts': getattr(h, 'layouts', []),
              'checks': h.checks, 'shots': h.shots, 'repo_data_unchanged': before == after, 'temp_files_removed': removed,
              'log': [line.replace(str(REPO), '<repo>').replace(str(h.tmp), '<qa-temp>') for line in h.log]}
    (out/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    print(f"completed={completed} error={error} PASS={report['passed']} FAIL={report['failed']}", flush=True)
    raise SystemExit(bool(error or report['failed'] or not completed))


if __name__ == '__main__':
    main()
