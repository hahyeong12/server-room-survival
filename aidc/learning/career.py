"""Phase9 ledger-derived assessment. No rewards, wall clock, or client-side arithmetic.

Operations use only facts in the request/incident ledger; learning uses only the learning record.
Rules (v2):
* contracts: on-time completions over decided requests (still-running requests are not judged yet);
* safety: an incident counts as unsafe only for a policy refusal (data deletion, UPS bypass, unconsented
  condition change) or an action tried before its required approval/consent. Refusals that are the engine's
  condition checks (no second uplink, no capacity to move, deadline no longer allows the change) are not penalised;
* learning interpretation: the first answer per incident. With the optional CLI (free shifts) each incident is
  judged by the first answer of every source the player used for it: the first CLI interpretation if the CLI was
  used, and the first decisive hypothesis if one was made. Unanswered CLI readings of a used incident score 0, and
  a wrong first answer in one source cannot be replaced from the other; repeats cannot farm.
* (v3) a refusal without a plan is unsafe only for the policy list (deletion, UPS bypass, batch change without
  consent); asking the customer where no condition change is needed is not unsafe.
"""
from result_summary import outcome_key
import hashlib
import json

VERSION = 3
# Actions the engine refuses by policy without a plan: data deletion, UPS bypass, a condition change without consent.
POLICY = frozenset({'delete_data', 'ups_bypass', 'reduce_batch'})
WEIGHTS = {'operations': {'contracts': 40, 'recovery': 25, 'safety': 20, 'communication': 15},
           'learning': {'evidence': 30, 'interpretation': 35, 'hypothesis': 25, 'independence': 10}}
RULE = ('first-interpretation-per-incident;unanswered-zero;required-probes-v1;per-incident-source-when-optional;'
        'decided-requests;policy-or-approval-refusals-only;policy-list;first-answer-of-every-used-source')
FINGERPRINT = hashlib.sha256(json.dumps([VERSION, WEIGHTS, RULE], sort_keys=True).encode()).hexdigest()


def _unsafe_refusal(session, rec, entry):
    if entry['result'] != 'refused' or entry.get('condition'):
        return False
    plan = session._tdef(rec)['actions'].get(entry['action'])
    if plan is None:
        return entry['action'] in POLICY   # e.g. ask_consent where no condition change is needed is not unsafe
    need = plan.get('requires', '')
    return need == 'consent' or need.startswith('approval:')


def assess(session):
    records = [r for r in (session.shift_records() if hasattr(session, 'shift_records') else []) if r.state not in ('armed', 'void')]
    runs = [session.runs[rid] for rid in session.shift_request_ids()]

    def ratio(n, d, weight):
        return round(weight * n / d) if d else None
    decided = [k for k in (outcome_key(r) for r in runs) if k != 'in_progress']
    safety = [a for r in records for a in r.actions if a['result'] in ('none', 'refused')]
    ops = {'contracts': ratio(sum(k == 'on_time' for k in decided), len(decided), 40),
           'recovery': ratio(sum(r.state == 'closed' for r in records), len(records), 25),
           'safety': ratio(sum(not any(_unsafe_refusal(session, r, a) for a in r.actions) for r in records), len(records), 20),
           # Phase 10 saves: every customer the incident affected (shared incidents); older saves: the own request.
           'communication': ratio(sum(session.notified_before_recovery(r) if hasattr(session, 'notified_before_recovery') else
                                      bool(r.notified) and (r.recovered is None or min(r.notified) <= r.recovered)
                                      for r in records), len(records), 15)}
    ids = {r.id for r in records}
    learning = getattr(session, 'linux', {}) or {}
    optional = getattr(session, 'learning_optional', False)
    answers = [x for x in learning.get('interpretations', []) if x['incident'] in ids]
    cli_used = {o.get('incident') for o in learning.get('observations', [])}
    hypotheses = [h for r in records for h in r.hypotheses]

    def reading(rec):
        cli = next((x['correct'] for x in answers if x['incident'] == rec.id), False)
        if learning and not optional:
            return cli
        decisive = next((h for h in rec.hypotheses if h['verdict'] != 'insufficient'), None)
        gui = decisive is not None and decisive['verdict'] == 'confirmed'
        # Optional terminal: every source the player used for this incident is judged by its own first answer, so a
        # wrong first answer in one source cannot be replaced by a later right answer in the other.
        if rec.id in cli_used:
            return cli and (decisive is None or gui)
        return gui

    def evidence_ok(rec):
        required = set(session.content.causes[rec.type]['probes'])
        return rec.diagnosed is not None and required <= {e['probe'] for e in rec.evidence}
    learn = {'evidence': ratio(sum(evidence_ok(r) for r in records), len(records), 30),
             'interpretation': ratio(sum(reading(r) for r in records), len(records), 35),
             'hypothesis': ratio(sum(h['verdict'] == 'confirmed' for h in hypotheses), len(hypotheses), 25),
             'independence': ratio(sum(not any(x['incident'] == r.id for x in learning.get('help', [])) for r in records), len(records), 10)}

    def total(parts, category):
        available = sum(WEIGHTS[category][k] for k, v in parts.items() if v is not None)
        return round(100 * sum(v for v in parts.values() if v is not None) / available) if available else None
    unsafe = [a['action'] for a in safety if a['action'] in ('delete_data', 'ups_bypass')]
    result = getattr(getattr(session, 'global_', None), 'result', None) or {}
    neglected = [x['id'] for x in (result.get('handoff') or {}).get('incidents', []) if x['class'] == 'neglect']
    handed = [x['id'] for x in (result.get('handoff') or {}).get('incidents', []) if x['class'] == 'handover']
    return {'version': VERSION, 'operations': {'score': total(ops, 'operations'), 'items': ops},
            'learning': {'score': total(learn, 'learning'), 'items': learn}, 'weights': WEIGHTS,
            'unsafe': unsafe, 'handedOver': handed, 'neglected': neglected, 'basis': {'requests': len(runs), 'decided': len(decided), 'incidents': len(records),
                                       'interpretations': len(answers), 'wrongOrRefusedActions': len(safety)},
            'notice': ('운영은 계약·복구·안전·소통, 학습은 근거·출력 해석·가설·도움 기록입니다. 해석은 사건별 첫 답을 평가하며 미응답은 0점입니다. '
                       '선택 사항인 터미널은 쓴 사건에서만 터미널 해석으로, 쓰지 않은 사건은 근거 있는 가설로 평가합니다. 반복 조회로 점수를 올릴 수 없습니다. '
                       '안전은 정책 위반·승인/동의 전 시도만 감점하며, 엔진이 조건을 확인해 거절한 시도(우회 경로 없음·이전 용량 부족 등)는 감점하지 않습니다. '
                       '실시간 대기·읽기·화면 이동·장애 발생 자체는 감점하지 않습니다. 평가 기회가 없는 항목은 제외합니다.')}
