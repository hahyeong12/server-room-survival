"""Phase 10 test helpers: make a save that looks exactly like one written before Phase 10 (no `ops_rules`).

A new Phase 10 save is created, its stored payload has the Phase 10 block and record fields removed, and the session
is reopened from disk. That is the shape every Phase 7~9 save has, so the published rules must apply to it.
"""
from __future__ import annotations

import json

from aidc.incidents.session import PHASE10_FIELDS


def strip_phase10(db):
    payload = db.get_simulation()
    payload.pop('ops_rules', None)
    for rec in (payload.get('incident') or {}).get('records', []):
        for key in PHASE10_FIELDS:
            rec.pop(key, None)
    with db.transaction():
        db.save_simulation(payload)
    return payload


def legacy(temp, factory, name):
    """factory(db) -> new session. Returns the same save reopened as a pre-Phase 10 save."""
    db = temp.db(name)
    s = factory(db)
    strip_phase10(db)
    db.close()
    temp.dbs.remove(db)
    reopened = factory(temp.db(name))
    assert not reopened.rules10
    return reopened


def payload_bytes(s):
    return json.dumps(s.db.get_simulation(), sort_keys=True, ensure_ascii=False)
