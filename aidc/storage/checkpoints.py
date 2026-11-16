"""장 시작 DB를 별도로 보존하고 재도전은 항상 새 슬롯으로 복사합니다."""
from pathlib import Path
import json
import sqlite3


def checkpoint_path(source, chapter):
    source = Path(source)
    if chapter not in (1, 2, 3, '3b', 'lab'):
        raise ValueError('알 수 없는 장입니다.')
    return source.with_name(f'aidc_checkpoint_{source.stem}_ch{chapter}.db')


def capture(session):
    from aidc.story.chapters import current_chapter
    if session.mode != 'story' or session.story.practice or session.db.path is None:
        return None
    target = checkpoint_path(session.db.path, current_chapter(session.story).key)
    try:
        with target.open('xb'):
            pass
    except FileExistsError:
        return target
    try:
        connection = sqlite3.connect(target)
        try:
            session.db.conn.backup(connection)
        finally:
            connection.close()
    except Exception:
        target.unlink()  # 이 호출에서 독점 생성한 파일만 정리합니다.
        raise
    return target


def restore(slots, source, chapter):
    from aidc.story.chapters import chapter_from_payload
    checkpoint = checkpoint_path(source, chapter)
    connection = sqlite3.connect(checkpoint.resolve().as_uri()+'?mode=ro', uri=True)
    try:
        row = connection.execute('SELECT payload FROM simulation_state WHERE id=1').fetchone()
        payload = json.loads(row[0]) if row else {}
        story = payload.get('story') if isinstance(payload, dict) else None
        if (not isinstance(story, dict) or payload.get('mode') != 'story' or story.get('practice')
                or chapter_from_payload(story).key != chapter):
            raise ValueError('체크포인트의 모드 또는 장이 현재 도전과 일치하지 않습니다.')
        target = slots.reserve_new()
        try:
            destination = sqlite3.connect(target)
            try:
                connection.backup(destination)
            finally:
                destination.close()
        except Exception:
            target.unlink()
            raise
        return target
    finally:
        connection.close()
