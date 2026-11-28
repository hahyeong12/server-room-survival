"""Phase 10 operating rules (versioned): one deadline formula, all affected customers, explicit handoff, impact forecast.

These rules are stamped into every *new* incident / Linux / senior / free-shift save as the payload block `ops_rules`.
A save without the block (made before Phase 10) keeps its published rules exactly; a save with an unknown stamp is
refused instead of being reinterpreted. Nothing here changes the incident v1 content or its fingerprints.

1. Deadline: every consent / deadline estimate uses the 10-minute ceiling of the real clock (`ceil10`), the same
   formula as GameState.estimate_minutes. Phase 7's `int(x + 9) // 10 * 10` could round 0.6 minutes down to 0 and
   approve a batch change that then finished 10 minutes after the due time. Finishing exactly at the due minute is on
   time everywhere (outcome_key: late only when completed > due).
2. Shared incidents: the set of requests an incident really affected (`impacted`, from the server ledger) is kept.
   A customer notice goes to every affected customer; "notified before recovery" means every one of them; the final
   report reaches all of them; the post-recovery observation window waits while any affected job still runs.
3. Handoff: an unresolved incident can be handed to the next shift explicitly. The shift then ends with a fixed result,
   the incident stays unresolved (never counted as resolved), and each item is classified: a responsible handoff
   (scope confirmed and every affected customer told) or neglect (an affected customer was never told).
4. Forecast: after the player's own diagnosis, each recovery path of that cause is tried on a rolled-back copy of the
   real engine (same ticks, approvals, consent, residual slowdown and limits), so the comparison is the engine's own.
"""
from __future__ import annotations

import hashlib
import json

ID = 'phase10-ops-v1'
RULES = {'deadline': 'ceil10-all-modes;due-inclusive', 'notify': 'all-impacted-customers',
         'verify': 'window-until-every-impacted-job-done', 'handoff': 'explicit-unresolved;responsible-vs-neglect',
         'forecast': 'rolled-back-engine;after-diagnosis;no-future-arrivals-or-incidents'}
FINGERPRINT = hashlib.sha256(json.dumps([ID, RULES], sort_keys=True).encode()).hexdigest()
FORECAST_CAP = 480          # virtual minutes a forecast follows (beyond: "not within 8 hours")
FIX_RESULTS = ('fix', 'isolate_move', 'isolate_repair')


def stamp():
    return {'id': ID, 'fingerprint': FINGERPRINT}


def load(saved):
    """None for a save made before Phase 10 (published rules kept); the stamp for a Phase 10 save."""
    if not saved:
        return stamp()
    value = saved.get('ops_rules')
    if value is None:
        return None
    if not isinstance(value, dict) or value.get('id') != ID or value.get('fingerprint') != FINGERPRINT:
        raise ValueError('이 저장은 다른 버전의 운영 규칙(기한·공유 장애·인계 판정)으로 만들어졌습니다. '
                         '규칙을 바꿔 다시 해석하지 않도록 열지 않습니다. 원본 저장은 보존됩니다.')
    return dict(value)


class Rollback(Exception):
    """Raised inside a forecast so the engine's own _atomic restores every in-memory and DB change."""
