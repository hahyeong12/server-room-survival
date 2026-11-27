"""Phase9 ledger-derived assessment. No rewards, wall clock, or client-side arithmetic."""
from result_summary import outcome_key

VERSION = 1
WEIGHTS = {'operations': {'contracts': 40, 'recovery': 25, 'safety': 20, 'communication': 15},
           'learning': {'evidence': 30, 'interpretation': 35, 'hypothesis': 25, 'independence': 10}}


def assess(session):
    records = [r for r in (session.shift_records() if hasattr(session, 'shift_records') else []) if r.state not in ('armed', 'void')]
    runs = [session.runs[rid] for rid in session.shift_request_ids()]
    def ratio(n, d, weight):
        return round(weight * n / d) if d else None
    requests = [outcome_key(r) for r in runs]
    safety = [a for r in records for a in r.actions if a['result'] in ('none', 'refused')]
    ops = {'contracts': ratio(sum(k == 'on_time' for k in requests), len(runs), 40),
           'recovery': ratio(sum(r.state == 'closed' for r in records), len(records), 25),
           'safety': ratio(sum(not any(a['result'] == 'refused' for a in r.actions) for r in records), len(records), 20),
           'communication': ratio(sum(bool(r.notified) and (r.recovered is None or min(r.notified) <= r.recovered)
                                      for r in records), len(records), 15)}
    ids = {r.id for r in records}
    learning = getattr(session, 'linux', {})
    answers = [x for x in learning.get('interpretations', []) if x['incident'] in ids]
    hypotheses = [h for r in records for h in r.hypotheses]
    # With no CLI curriculum, use the actual evidence-grounded hypothesis record for interpretation.
    readings = answers if learning else [{'correct': h['verdict'] == 'confirmed'} for h in hypotheses if h['verdict'] != 'insufficient']
    learn = {'evidence': ratio(sum(r.diagnosed is not None and len({e['probe'] for e in r.evidence}) >= 2 for r in records), len(records), 30),
             'interpretation': ratio(sum(x['correct'] for x in readings), len(readings), 35),
             'hypothesis': ratio(sum(h['verdict'] == 'confirmed' for h in hypotheses), len(hypotheses), 25),
             'independence': ratio(sum(not any(x['incident'] == r.id for x in learning.get('help', [])) for r in records), len(records), 10)}
    def total(parts, category):
        available = sum(WEIGHTS[category][k] for k, v in parts.items() if v is not None)
        return round(100 * sum(v for v in parts.values() if v is not None) / available) if available else None
    unsafe = [a['action'] for a in safety if a['action'] in ('delete_data', 'ups_bypass')]
    return {'version': VERSION, 'operations': {'score': total(ops, 'operations'), 'items': ops},
            'learning': {'score': total(learn, 'learning'), 'items': learn}, 'weights': WEIGHTS,
            'unsafe': unsafe, 'basis': {'requests': len(runs), 'incidents': len(records), 'interpretations': len(answers),
                                       'wrongOrRefusedActions': len(safety)},
            'notice': '운영은 계약·복구·안전·소통, 학습은 근거·출력 해석·가설·도움 기록입니다. 실시간 대기·설명 읽기·화면 이동·장애 발생 자체는 감점하지 않습니다. 해당 기회가 없는 항목은 제외해 100점으로 환산합니다.'}
