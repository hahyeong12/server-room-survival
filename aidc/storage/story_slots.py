"""기존 스토리를 보존하는 독립 파일 슬롯. 기존 파일은 재사용/초기화하지 않습니다."""
from pathlib import Path
import json
import re
import sqlite3

from database import STORY_DB_PATH


class StorySlots:
    pattern = re.compile(r'aidc_story_slot_([0-9]+)\.db')

    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else STORY_DB_PATH.parent
        self.directory = self.directory.resolve()
        self.legacy_path = self.directory / STORY_DB_PATH.name

    def available(self):
        paths = [p for p in self.directory.glob('aidc_story_slot_*.db')
                 if p.is_file() and self.pattern.fullmatch(p.name)]
        paths.sort(key=lambda p: int(self.pattern.fullmatch(p.name)[1]))
        if self.legacy_path.is_file():
            paths.insert(0, self.legacy_path)
        return paths

    def payload(self, path):
        """메뉴 조회는 SQLite를 읽기 전용으로 열며 손상된 슬롯도 목록에서 숨기지 않습니다."""
        try:
            connection = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True, timeout=0.2)
            try:
                row = connection.execute('SELECT payload FROM simulation_state WHERE id=1').fetchone()
                data = json.loads(row[0]) if row else {}
                return data if isinstance(data, dict) else {}
            finally:
                connection.close()
        except (OSError, sqlite3.Error, ValueError):
            return {}

    def category(self, path):
        data = self.payload(path)
        if data.get('mode') == 'tutorial':
            return 'tutorial'
        story = data.get('story')
        return 'practice' if isinstance(story, dict) and story.get('practice') is True else 'story'

    def for_mode(self, category):
        return [path for path in self.available() if self.category(path) == category]

    def reserve_new(self):
        """독점 생성으로 연속 클릭이나 별도 프로세스에서도 기존 파일을 덮어쓰지 않습니다."""
        number = max((int(self.pattern.fullmatch(p.name)[1]) for p in self.available()
                      if self.pattern.fullmatch(p.name)), default=0) + 1
        while True:
            path = self.directory / f'aidc_story_slot_{number:03d}.db'
            try:
                with path.open('xb'):
                    pass
            except FileExistsError:
                number += 1
            else:
                return path

    def describe(self, path):
        """읽기 전용 진행 위치. 단계 종료를 미션 성공으로 단정하지 않습니다."""
        from aidc.story.chapters import chapter_from_payload
        if not Path(path).is_file():
            return ''
        data = self.payload(path)
        story = data.get('story')
        if not isinstance(story, dict):
            return ' · 시작 전' if not data else ''
        intro = story.get('onboarding')
        if isinstance(intro, dict) and not story.get('chapter2'):
            title = '짧은 튜토리얼' if intro.get('kind') == 'tutorial' else '제1장 — 첫 근무'
            return f' · {title} · 완료 업무 {self._count(intro.get("completed"))}/{1 if intro.get("kind") == "tutorial" else 3}'
        if data.get('mode') == 'tutorial':
            return ' · 튜토리얼 '+('완료' if story.get('chapter_completed') else '진행 중')
        chapter = chapter_from_payload(story)
        prefix = chapter.heading+(' · 연습' if story.get('practice') else '')
        if chapter.key == 'lab':
            t = story['training']
            prefix += ' · Engineering Lab 연습' if t.get('practice') else ' · 심화 연수'
            return ' · '+prefix+f' · 학습 과제 {self._count(t.get("completed"))}/5'
        field = {2: 'chapter2', 3: 'chapter3', '3b': 'chapter3b'}.get(chapter.key)
        done = (self._count(story[field].get('completed_steps')) >= (6 if chapter.key == 2 else 11)) if field else story.get('chapter_completed')
        return ' · '+prefix+(' · 종료 · 결과 확인' if done else ' · 진행 중')

    def chapter3_in_progress(self):
        return self._in_progress('chapter3', 'chapter3b')

    def chapter3b_in_progress(self):
        return self._in_progress('chapter3b', 'training')

    @staticmethod
    def _count(value):
        return len(value) if isinstance(value, list) else 0

    def _in_progress(self, field, following):
        paths = []
        for path in self.available():
            story = self.payload(path).get('story')
            if not isinstance(story, dict):
                continue
            chapter = story.get(field)
            if isinstance(chapter, dict) and not story.get(following) and self._count(chapter.get('completed_steps')) < 11:
                paths.append(path)
        return paths

    def title(self, path):
        match = self.pattern.fullmatch(Path(path).name)
        return (f'새 스토리 {int(match[1])}' if match else '기존 스토리') + f' · {Path(path).name}'
