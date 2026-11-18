"""실험용 Windows DPI 인식과 UI 배율(dpi-review-001).

기본 실행은 지금과 같은 DPI 비인식이며 배율은 1.0입니다. 이때 Windows가 96DPI로 그린 창을 화면 배율만큼
비트맵으로 늘려 보여 주므로 125% 화면에서 글자가 흐립니다.

환경 변수 ``SRS_DPI_AWARE=system``일 때만 Tk 창을 만들기 전에 System DPI Aware를 켭니다.
켜면 Tk는 실제 DPI로 글꼴(pt 단위)을 그리지만 px 단위 레이아웃(창 크기, Canvas 좌표, wraplength)은
그대로입니다. 그래서 설정 성공과 실제 인식 상태를 확인한 경우에만 ``GetDpiForSystem()/96``을 배율로
쓰고, 화면 코드는 ``px()``·``finish_canvas()``로 px 값을 같은 비율로 늘립니다.
실패하면 배율은 1.0으로 남습니다(비인식 상태에서는 1.0이 올바른 값입니다).
Per-Monitor DPI 인식은 Tk 8.6이 지원하지 않아 범위 밖입니다.
"""
import os
import sys

ENV = 'SRS_DPI_AWARE'
PROCESS_SYSTEM_DPI_AWARE = 1
E_ACCESSDENIED = -2147024891  # 0x80070005: 이미 인식 상태가 정해진 프로세스
BASE_DPI = 96

_state = {}


def _reset():
    _state.clear()
    _state.update(mode='unaware', scale=1.0, dpi=BASE_DPI, requested=False, reason='기본 실행(DPI 비인식)')


_reset()


def requested(environ=None):
    """실험 플래그가 켜져 있는지(환경 변수 SRS_DPI_AWARE=system)."""
    return (os.environ if environ is None else environ).get(ENV, '').strip().lower() == 'system'


class WindowsApi:
    """실제 Win32 호출. 테스트에서는 같은 메서드를 가진 가짜 객체를 넘깁니다."""

    def __init__(self):
        import ctypes
        self.ctypes = ctypes
        self.shcore = ctypes.windll.shcore
        self.user32 = ctypes.windll.user32

    def set_process_awareness(self, value):
        return self.shcore.SetProcessDpiAwareness(value)

    def process_awareness(self):
        value = self.ctypes.c_int(-1)
        if self.shcore.GetProcessDpiAwareness(None, self.ctypes.byref(value)) != 0:
            return None
        return value.value

    def system_dpi(self):
        return self.user32.GetDpiForSystem()


def enable_system_awareness(api=None):
    """System DPI Aware를 켜고 배율을 정합니다. Tk 창을 만들기 전에 한 번만 부릅니다.

    반환값은 성공 여부입니다. 설정 호출이 실패했거나, 호출 뒤 실제 상태가 System Aware가 아니거나,
    DPI 값이 비정상이면 배율을 바꾸지 않습니다(1.0 유지)."""
    _state['requested'] = True
    if _state['mode'] == 'system':
        return True
    if api is None:
        if sys.platform != 'win32':
            _state['reason'] = 'Windows가 아니어서 적용하지 않음'
            return False
        try:
            api = WindowsApi()
        except Exception as exc:  # shcore가 없는 오래된 Windows 등
            _state['reason'] = f'DPI API를 불러오지 못함: {exc!r}'
            return False
    try:
        result = api.set_process_awareness(PROCESS_SYSTEM_DPI_AWARE)
        actual = api.process_awareness()
        if result not in (0, E_ACCESSDENIED):
            _state['reason'] = f'SetProcessDpiAwareness 실패(HRESULT {result})'
            return False
        if actual != PROCESS_SYSTEM_DPI_AWARE:
            # E_ACCESSDENIED는 이미 다른 상태로 정해진 경우입니다. 실제 상태가 System Aware일 때만 받아들입니다.
            _state['reason'] = f'실제 DPI 인식 상태가 System Aware가 아님({actual})'
            return False
        dpi = int(api.system_dpi())
    except Exception as exc:
        _state['reason'] = f'DPI 확인 중 오류: {exc!r}'
        return False
    if not BASE_DPI <= dpi <= BASE_DPI*5:
        _state['reason'] = f'비정상 시스템 DPI({dpi})'
        return False
    _state.update(mode='system', dpi=dpi, scale=dpi/BASE_DPI, reason='System DPI Aware 적용')
    return True


def configure_from_environment(environ=None, api=None):
    """main()이 Tk를 만들기 전에 부릅니다. 플래그가 없으면 아무것도 하지 않습니다(기본 동작 유지)."""
    if not requested(environ):
        return False
    return enable_system_awareness(api)


def status():
    return dict(_state)


def scale():
    return _state['scale']


def px(value):
    """설계 기준(96DPI) px 값을 현재 화면 px로 바꿉니다. 배율 1.0이면 값을 그대로 돌려줍니다."""
    s = _state['scale']
    if s == 1.0:
        return value
    if isinstance(value, int):
        return int(round(value*s))
    return value*s


def size(pair):
    return tuple(px(v) for v in pair)


def unpx(value):
    """화면 px를 설계 기준 px로 되돌립니다(실제 위젯 크기를 기준값과 비교할 때)."""
    s = _state['scale']
    return value if s == 1.0 else value/s


def geometry(spec):
    """'1000x650+40+20' 같은 Tk geometry 문자열의 숫자를 배율에 맞춥니다."""
    if _state['scale'] == 1.0:
        return spec
    import re
    return re.sub(r'\d+', lambda m: str(px(int(m.group()))), spec)


def logical_size(canvas):
    """Canvas의 실제 크기를 설계 기준 px로 돌려줍니다. 그린 뒤 finish_canvas()로 다시 늘립니다."""
    return unpx(canvas.winfo_width()), unpx(canvas.winfo_height())


def finish_canvas(canvas, tag='all'):
    """설계 기준 좌표로 그린 Canvas 항목의 좌표만 배율만큼 늘립니다.

    글꼴은 이미 Tk가 실제 DPI로 키우므로 다시 늘리지 않습니다(Canvas.scale은 좌표만 바꿉니다)."""
    s = _state['scale']
    if s != 1.0:
        canvas.scale(tag, 0, 0, s, s)
