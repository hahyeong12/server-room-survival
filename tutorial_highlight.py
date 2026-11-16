"""한 번에 한 조작 대상만 강조하는 화면 전용 구성요소. 저장/게임 상태는 수정하지 않습니다.

대상이 `tutorial_parts()`(버튼 묶음)를 제공하면 묶음 전체를 둘러싸지 않고 각 버튼에만 금색 테두리를 칩니다.
예: [⏩ 시간 빨리감기] 묶음은 라벨과 버튼 사이 빈 공간을 빼고 [+10분] [+30분] [+60분] 각각을 강조합니다.
"""
import tkinter as tk

GOLD, GOLD_DIM = '#ffe08a', '#d9ae54'
TINT = '#3c3019'
TAB_KEYS = {'inspector': 0, 'preview': 1}
POINTER_TEXT = {'time': '시간 빨리감기로 작업을 진행하세요', 'work_complete': '시간 빨리감기로 작업을 진행하세요'}
STYLE_KEYS = ('highlightthickness', 'highlightbackground', 'highlightcolor')


def pointer_geometry(rect, container, size, gap=3):
    """대상 사각형(rect=(x,y,w,h), 컨테이너 좌표) 중앙을 가리키는 안내 위치를 계산합니다.
    위쪽 공간이 부족하면 아래쪽에 놓고 below=True를 돌려줍니다. 반환: (x, y, below, arrow_x).
    arrow_x는 안내 상자 안에서 대상 중심이 오는 가로 위치로, 상자가 화면 가장자리에 밀려도 대상을 가리킵니다."""
    x, y, w, h = rect
    cw, ch = container
    pw, ph = size
    center = x+w/2
    px = max(0, min(round(center-pw/2), max(0, cw-pw)))
    below = y-ph-gap < 0
    py = y+h+gap if below else y-ph-gap
    py = max(0, min(py, max(0, ch-ph)))
    return px, py, below, max(0, min(round(center-px), pw))


def edge_rect(rect, inset, thickness, side):
    """대상 사각형 바깥에 붙는 테두리 한 변의 위치(순수 함수). inset 0은 3px 바깥 굵은 선, 그 외는 1px 바깥 가는 선."""
    x, y, width, height = rect
    offset = -3 if inset == 0 else -1
    ex, ey, ew, eh = x+offset, y+offset, width-2*offset, height-2*offset
    if side in ('top', 'bottom'):
        return ex, (ey if side == 'top' else ey+eh-thickness), ew, thickness
    return (ex if side == 'left' else ex+ew-thickness), ey, thickness, eh


def clip_rect(rect, clips):
    """rect=(x, y, w, h)를 상위 영역들(clips)과 교차한 사각형(순수 함수). 겹치는 부분이 없으면 None."""
    x0, y0, x1, y1 = rect[0], rect[1], rect[0]+rect[2], rect[1]+rect[3]
    for cx, cy, cw, ch in clips:
        x0, y0, x1, y1 = max(x0, cx), max(y0, cy), min(x1, cx+cw), min(y1, cy+ch)
        if x1 <= x0 or y1 <= y0:
            return None
    return x0, y0, x1-x0, y1-y0


def mostly_visible(rect, clips, ratio=0.9):
    """상위 영역에 잘리지 않고 대부분(기본 90%)이 보이는지(순수 함수)."""
    inside = clip_rect(rect, clips)
    return inside is not None and rect[2] > 0 and rect[3] > 0 and inside[2]*inside[3] >= ratio*rect[2]*rect[3]


def widget_visible(widget):
    """대상이 실제 화면에서 보이고 눌리는지 확인합니다. 상위 프레임에 잘렸거나(창 높이 부족), 중심점이 다른 위젯에
    덮였으면 False입니다. QA tutorial-001 Q-01: 가려진 버튼의 좌표에 금색 테두리가 그려져 엉뚱한 글자를 감쌌습니다."""
    try:
        if not widget.winfo_ismapped() or not widget.winfo_viewable():
            return False
        top = widget.winfo_toplevel()
        rect = (widget.winfo_rootx(), widget.winfo_rooty(), widget.winfo_width(), widget.winfo_height())
        clips, parent = [], widget.master
        while parent is not None and parent is not top:
            clips.append((parent.winfo_rootx(), parent.winfo_rooty(), parent.winfo_width(), parent.winfo_height()))
            parent = parent.master
        clips.append((top.winfo_rootx(), top.winfo_rooty(), top.winfo_width(), top.winfo_height()))
        if not mostly_visible(rect, clips):
            return False
        hit = widget.winfo_containing(rect[0]+rect[2]//2, rect[1]+rect[3]//2)
        if hit is None:
            return False
        # 강조 테두리·안내 자체는 대상 위에 겹쳐 있어도 됩니다.
        return str(hit).startswith(str(widget)) or getattr(hit, 'tutorial_side', None) is not None
    except tk.TclError:
        return False


def highlight_parts(widget):
    """강조할 실제 조작 버튼 목록. 묶음(tutorial_parts)이면 각 버튼, 묶음이 아니면 빈 목록입니다."""
    parts = getattr(widget, 'tutorial_parts', None)
    parts = list(parts() if callable(parts) else parts or ())
    return [part for part in parts if hasattr(part, 'invoke')]


class TutorialHighlight:
    def __init__(self, root, animate=True):
        self.root, self.animate = root, animate
        self.target = self.key = self.timer = None
        self.original = None
        self.target_binding = None
        self.top = self.top_binding = None
        self.custom = False
        self.edges = []
        self.parts, self.part_originals = [], []
        self.pointer = None
        self.bright = True
        self.hidden = False  # 대상이 가려져 테두리를 숨긴 상태(화면 전용)
        self.binding = root.bind('<Destroy>', self._destroyed, add='+')
        self.layout_binding = root.bind('<Configure>', lambda _: self.position_pointer(), add='+')

    def _destroyed(self, event):
        if event.widget is self.root:
            self.stop()
        elif event.widget is self.target:
            self.clear()

    def clear(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        if self.target is not None and self.target.winfo_exists():
            if self.target_binding is not None:
                self.target.unbind('<Destroy>', self.target_binding)
            if self.custom:
                self.target.set_tutorial_highlight(None)
            elif self.original:
                self.target.configure(**self.original)
        # 묶음 강조: 각 버튼의 원래 스타일을 복구합니다.
        for part, original in zip(self.parts, self.part_originals):
            try:
                if part.winfo_exists():
                    part.configure(**original)
            except tk.TclError:
                pass
        self.parts, self.part_originals = [], []
        for edge in self.edges:
            if edge.winfo_exists():
                edge.destroy()
        self.edges.clear()
        if self.pointer is not None:
            self.pointer.destroy()
            self.pointer = None
        if self.top is not None and self.top_binding is not None:
            try:
                self.top.unbind('<Configure>', self.top_binding)
            except tk.TclError:
                pass
        self.top = self.top_binding = None
        self.target = self.key = self.original = None
        self.target_binding = None
        self.custom = False

    def _make_edges(self, top, part=None):
        # 형제 위젯으로 그려 Windows 기본 버튼의 자체 그리기에 묻히지 않게 합니다.
        for inset, thickness in ((0, 3), (5, 1)):
            for side in ('top', 'bottom', 'left', 'right'):
                edge = tk.Frame(top, bg=GOLD, bd=0, cursor='hand2')
                edge.tutorial_side = (inset, thickness, side)
                edge.tutorial_part = part
                edge.bind('<Button-1>', lambda _, p=part: p.invoke() if p is not None else self.activate())
                self.edges.append(edge)

    def show(self, key=None, widget=None, pointer=True):
        """pointer=False: 같은 행동을 이미 다른 곳(목표 카드)이 알려 주므로 별도 클릭 안내를 띄우지 않습니다."""
        if widget is self.target and key == self.key:
            return
        self.clear()
        if widget is None or not widget.winfo_exists():
            return
        self.key, self.target, self.bright = key, widget, True
        self.custom = key in ('server', *TAB_KEYS) and hasattr(widget, 'set_tutorial_highlight')
        self.target_binding = widget.bind('<Destroy>', self._destroyed, add='+')
        top = widget.winfo_toplevel()
        if top is not self.root:
            # 팝업 안의 대상은 팝업이 이동/크기 변경될 때 바로 다시 배치합니다.
            self.top, self.top_binding = top, top.bind('<Configure>', lambda _: self.position_pointer(), add='+')
        parts = [] if self.custom else highlight_parts(widget)
        if parts:
            # 묶음 프레임 자체(라벨·빈 공간 포함)는 강조하지 않고 실제 버튼마다 테두리를 칩니다.
            self.parts = parts
            self.part_originals = [{name: part.cget(name) for name in ('bg', 'fg')} if 'foreground' in part.keys() else {}
                                   for part in parts]
            for part in parts:
                if 'foreground' in part.keys():
                    part.configure(bg=TINT, fg=GOLD)
                self._make_edges(top, part)
            pointer = False  # 버튼 위나 주변 정보를 가리지 않게 별도 안내를 띄우지 않습니다.
        elif not self.custom:
            self.original = {name: widget.cget(name) for name in STYLE_KEYS}
            if 'foreground' in widget.keys():
                self.original.update(bg=widget.cget('bg'), fg=widget.cget('fg'))
                widget.configure(bg=TINT, fg=GOLD)
            self._make_edges(top)
        if pointer:
            self.pointer = tk.Label(top, text=POINTER_TEXT.get(key, '여기를 클릭')+'\n▼', justify='center', bg='#251f15', fg=GOLD,
                                    font=('Malgun Gothic', 9, 'bold'), padx=7, pady=2, cursor='hand2')
            self.pointer.bind('<Button-1>', lambda _: self.activate())
        self._paint()

    def activate(self):
        if self.target is None:
            return
        if self.key == 'preview':
            self.target.show_preview()
        elif self.key == 'inspector':
            self.target.book.select(self.target.inspector_frame)
        elif self.parts:
            self.parts[0].invoke()  # 묶음의 첫 실제 버튼(+10분)과 같은 동작
        elif self.key in ('time', 'work_complete'):
            next(w for w in self.target.winfo_children() if hasattr(w, 'invoke')).invoke()
        elif self.key == 'server':
            self.target.select('A')
        elif hasattr(self.target, 'invoke'):
            self.target.invoke()

    def _rect(self, widget, top):
        return (widget.winfo_rootx()-top.winfo_rootx(), widget.winfo_rooty()-top.winfo_rooty(),
                widget.winfo_width(), widget.winfo_height())

    def position_pointer(self):
        if self.target is None or not self.target.winfo_exists():
            return
        top = self.target.winfo_toplevel()
        if self.key == 'server':
            # 랙에는 Canvas 내부의 별도 클릭 안내를 표시합니다.
            if self.pointer is not None:
                self.pointer.place_forget()
            return
        if self.key in TAB_KEYS and hasattr(self.target, 'tutorial_rect'):
            # 탭은 패널 전체가 아니라 실제 탭 영역을 가리킵니다. 탭이 보이지 않으면 안내도 숨깁니다.
            rect = self.target.tutorial_rect(TAB_KEYS[self.key])
            if rect is None:
                if self.pointer is not None:
                    self.pointer.place_forget()
                return
            rect = (rect[0]-top.winfo_rootx(), rect[1]-top.winfo_rooty(), rect[2], rect[3])
        else:
            rect = self._rect(self.target, top)
        visible = {}
        for edge in self.edges:
            part = edge.tutorial_part
            if part is not None and not part.winfo_exists():
                continue
            widget = part if part is not None else self.target
            if widget not in visible:
                visible[widget] = widget_visible(widget)
            if not visible[widget]:
                # 가려지거나 잘린 대상에는 테두리를 그리지 않습니다(다른 위젯 위의 엉뚱한 테두리 방지).
                edge.place_forget()
                continue
            ex, ey, ew, eh = edge_rect(self._rect(part, top) if part is not None else rect, *edge.tutorial_side)
            edge.place(x=ex, y=ey, width=ew, height=eh)
            edge.lift()
        self.hidden = bool(visible) and not any(visible.values())
        if self.pointer is None or not self.pointer.winfo_exists():
            return
        if self.hidden:
            self.pointer.place_forget()
            return
        base = POINTER_TEXT.get(self.key, '여기를 클릭')
        self.pointer.update_idletasks()
        size = (self.pointer.winfo_reqwidth(), self.pointer.winfo_reqheight())
        px, py, below, _ = pointer_geometry(rect, (top.winfo_width(), top.winfo_height()), size)
        # 화살표를 문구 아래/위의 가운데 줄에 두어 상자 중심(=대상 중심)을 정확히 가리킵니다.
        text = ('▲\n'+base) if below else (base+'\n▼')
        if self.pointer.cget('text') != text:
            self.pointer.configure(text=text)
            size = (self.pointer.winfo_reqwidth(), self.pointer.winfo_reqheight())
            px, py, below, _ = pointer_geometry(rect, (top.winfo_width(), top.winfo_height()), size)
        self.pointer.place(x=px, y=py)
        self.pointer.lift()

    def _paint(self):
        self.timer = None
        if self.target is None or not self.target.winfo_exists():
            self.clear()
            return
        color = GOLD if self.bright else GOLD_DIM
        if self.custom:
            if self.key in TAB_KEYS:
                self.target.set_tutorial_highlight(color, TAB_KEYS[self.key])
            else:
                self.target.set_tutorial_highlight(color)
        else:
            if not self.parts:
                self.target.configure(highlightbackground=color, highlightcolor=color)
            for edge in self.edges:
                edge.configure(bg=color if edge.tutorial_side[0] == 0 else '#b28131')
        self.position_pointer()
        if self.pointer is not None:
            self.pointer.configure(fg=color)
        if self.animate:
            self.bright = not self.bright
            self.timer = self.root.after(500, self._paint)

    def stop(self):
        self.clear()
        if self.binding is not None:
            self.root.unbind('<Destroy>', self.binding)
            self.binding = None
        if self.layout_binding is not None:
            self.root.unbind('<Configure>', self.layout_binding)
            self.layout_binding = None
