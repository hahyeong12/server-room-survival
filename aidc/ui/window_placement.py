"""부모 창과 해당 모니터의 작업 영역을 기준으로 팝업을 배치합니다.

중앙 배치는 '계산 → 표시 → 실제 좌표 측정 → 차이가 있으면 한 번 보정' 순서입니다. 함수가 호출됐다는 사실이 아니라
실제 클라이언트 영역의 중심이 부모 최상위 창 중심과 맞는지로 확인합니다(dialog.placement에 기록).
환경 변수 SRS_PLACEMENT_LOG=1이면 계산값과 실제값을 출력합니다(수동 확인용).
"""
import os
import sys


def work_area(parent):
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes

        class MonitorInfo(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT),
                        ('work', wintypes.RECT), ('flags', wintypes.DWORD)]

        user = ctypes.windll.user32
        user.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user.MonitorFromWindow.restype = wintypes.HANDLE
        user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        monitor = user.MonitorFromWindow(parent.winfo_id(), 2)
        if user.GetMonitorInfoW(monitor, ctypes.byref(info)):
            r = info.work
            return r.left, r.top, r.right, r.bottom
    x, y = parent.winfo_vrootx(), parent.winfo_vrooty()
    return x, y, x + parent.winfo_vrootwidth(), y + parent.winfo_vrootheight()


def centered_bounds(parent_bounds, area, size, margin=12, decoration=(16, 40)):
    left, top, right, bottom = area
    width = min(size[0], max(1, right-left-2*margin-decoration[0]))
    height = min(size[1], max(1, bottom-top-2*margin-decoration[1]))
    px, py, pw, ph = parent_bounds
    x = max(left+margin, min(round(px+(pw-width)/2), right-margin-width-decoration[0]))
    y = max(top+margin, min(round(py+(ph-height)/2), bottom-margin-height-decoration[1]))
    return width, height, x, y


def frame_offset(dialog, parent):
    """창틀(제목줄·테두리) 바깥 좌표와 클라이언트 좌표의 차이. 숨긴(withdraw) 창은 아직 틀 정보가 없어 0으로 나오므로,
    같은 방식으로 꾸며진 부모 창의 차이를 대신 씁니다(대화창이 제목줄 높이만큼 아래로 치우치는 것을 막음)."""
    dx, dy = dialog.winfo_rootx()-dialog.winfo_x(), dialog.winfo_rooty()-dialog.winfo_y()
    if (dx, dy) == (0, 0) and not dialog.winfo_viewable():
        dx, dy = parent.winfo_rootx()-parent.winfo_x(), parent.winfo_rooty()-parent.winfo_y()
    return max(0, dx), max(0, dy)


def corrected_outer(outer, target_client, actual_client, tolerance=1):
    """표시 뒤 실제 클라이언트 좌표가 목표와 다르면 창틀 좌표를 그 차이만큼 옮긴 값을 돌려줍니다(순수 함수).
    차이가 허용 범위 안이면 None(보정 불필요)입니다."""
    ddx, ddy = target_client[0]-actual_client[0], target_client[1]-actual_client[1]
    if abs(ddx) <= tolerance and abs(ddy) <= tolerance:
        return None
    return outer[0]+ddx, outer[1]+ddy


def placement_record(parent_bounds, size, target_client, actual_client):
    """부모 중심과 실제 대화창 중심을 비교한 기록(순수 함수). 수동 확인·테스트에 씁니다."""
    px, py, pw, ph = parent_bounds
    width, height = size
    parent_center = (px+pw/2, py+ph/2)
    actual_center = (actual_client[0]+width/2, actual_client[1]+height/2)
    return {'parent_center': parent_center, 'target_client': tuple(target_client), 'actual_client': tuple(actual_client),
            'actual_center': actual_center,
            'offset': (round(actual_center[0]-parent_center[0]), round(actual_center[1]-parent_center[1]))}


def _move_outer(dialog, x, y):
    dialog.geometry(f'{x:+d}{y:+d}')
    if sys.platform == 'win32' and (x < 0 or y < 0):
        # Tk의 음수 geometry는 화면 오른쪽/아래로부터의 거리이므로 Win32로 직접 옮깁니다.
        import ctypes
        from ctypes import wintypes
        user = ctypes.windll.user32
        user.GetParent.argtypes = [wintypes.HWND]
        user.GetParent.restype = wintypes.HWND
        user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user.SetWindowPos(user.GetParent(dialog.winfo_id()), None, x, y, 0, 0, 0x15)


def center_dialog(dialog, parent, size=(820, 470), minimum=(740, 430)):
    # 부모가 창 안의 프레임이어도 기준은 그 프레임이 속한 최상위 창(관제실 전체 화면 영역)입니다.
    parent = parent.winfo_toplevel()
    parent.update_idletasks()
    bounds = (parent.winfo_rootx(), parent.winfo_rooty(), parent.winfo_width(), parent.winfo_height())
    area = work_area(parent)
    width, height, x, y = centered_bounds(bounds, area, size)
    target = (x, y)  # 원하는 클라이언트 영역 왼쪽 위
    dialog.minsize(min(minimum[0], width), min(minimum[1], height))
    # geometry의 좌표는 창틀 기준이고 Tk 위젯 좌표는 클라이언트 기준입니다.
    dx, dy = frame_offset(dialog, parent)
    x, y = max(area[0]+12, x-dx), max(area[1]+12, y-dy)
    target = (x+dx, y+dy)  # 화면 경계로 밀린 경우에도 같은 기준으로 비교합니다.
    dialog.geometry(f'{width}x{height}{x:+d}{y:+d}')
    if sys.platform == 'win32' and (x < 0 or y < 0):
        # Tk의 음수 geometry는 화면 오른쪽/아래로부터의 거리입니다.
        import ctypes
        from ctypes import wintypes
        dialog.update_idletasks()
        user = ctypes.windll.user32
        user.GetParent.argtypes = [wintypes.HWND]
        user.GetParent.restype = wintypes.HWND
        user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user.SetWindowPos(user.GetParent(dialog.winfo_id()), None, x, y, 0, 0, 0x15)
    dialog.deiconify()
    # 실제로 놓인 클라이언트 좌표를 측정하고, 창틀 추정이 틀렸다면 그 차이만큼 한 번 보정합니다.
    try:
        dialog.update_idletasks()
        actual = (dialog.winfo_rootx(), dialog.winfo_rooty())
        fixed = corrected_outer((x, y), target, actual)
        if fixed is not None:
            _move_outer(dialog, *fixed)
            dialog.update_idletasks()
            actual = (dialog.winfo_rootx(), dialog.winfo_rooty())
        dialog.placement = placement_record(bounds, (width, height), target, actual)
        if os.environ.get('SRS_PLACEMENT_LOG') == '1':
            print('[placement]', dialog.title(), dialog.placement, flush=True)
    except Exception:  # 측정 실패는 배치 자체를 막지 않습니다.
        pass


def nearby_bounds(anchor, area, size, avoid=(), gap=14):
    """조작 영역을 피하는 가까운 위치를 우선하고 화면 안으로 제한합니다."""
    ax, ay, aw, ah = anchor
    left, top, right, bottom = area
    width = min(size[0], right-left-32)
    height = min(size[1], bottom-top-56)
    candidates = ((ax, ay-height-gap-32), (ax+aw+gap, ay),
                  (ax-width-gap-16, ay), (ax, ay+ah+gap))
    def overlap(x, y, rect):
        rx, ry, rw, rh = rect
        return max(0, min(x+width+16, rx+rw)-max(x, rx)) * max(0, min(y+height+32, ry+rh)-max(y, ry))
    positions = [(max(left+8, min(x, right-width-24)),
                  max(top+8, min(y, bottom-height-40))) for x, y in candidates]
    x, y = min(positions, key=lambda p: (sum(overlap(*p, rect) for rect in (anchor, *avoid)),
                                       abs(p[0]-ax)+abs(p[1]-ay)))
    return width, height, x, y


def place_near(dialog, parent, anchor, size=(390, 210), avoid=()):
    parent.update_idletasks()
    width, height, x, y = nearby_bounds(anchor, work_area(parent), size, avoid)
    dialog.geometry(f'{width}x{height}{x:+d}{y:+d}')
    # center_dialog과 같은 음수 모니터 좌표 처리.
    if sys.platform == 'win32' and (x < 0 or y < 0):
        import ctypes
        from ctypes import wintypes
        dialog.update_idletasks()
        user = ctypes.windll.user32
        user.GetParent.argtypes = [wintypes.HWND]
        user.GetParent.restype = wintypes.HWND
        user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user.SetWindowPos(user.GetParent(dialog.winfo_id()), None, x, y, 0, 0, 0x15)
    dialog.deiconify()  # 위치를 정한 뒤에 한 번만 보여 줍니다.
