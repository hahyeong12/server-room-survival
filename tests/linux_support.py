"""Phase8 tests: only OS temporary SQLite files, engine actions, no GUI."""
from aidc.learning.linux_session import LinuxSession
from aidc.learning.linux_catalog import BY_ID, example
from aidc.learning.linux_curriculum import CASES
from aidc.learning.linux_terminal import job_servers
from tests.incident_support import start_open, fix, where

def opened(temp, cause='dns', shift=1, practice=True):
    s = LinuxSession(temp.db(f'linux_{len(temp.dbs)}.db'), shift=shift,
                     practice=cause if practice else None, seed=5)
    s.confirm_shift_briefing()
    start_open(s)
    for _ in range(15):
        if s.incident.records[0].state != 'armed':
            break
        s.advance_time(10)
    rec = s.incident.records[0]
    s.incident_ack(rec.id)
    return s, rec

def command(s, rec, ident, interpret=False, node=None, target=None):
    c = BY_ID[ident]
    node = node or {'any': 'noc', 'network': 'network', 'cluster': 'cluster',
                    'worker': f'server-{job_servers(s, rec)[0]}'}[c.context]
    line = example(c)
    if ident == 'ping' and rec.type == 'tor_uplink' and target is None:
        line = line.replace('10.20.0.15', f'10.20.{11 + "ABCD".index(rec.primary)}.15')
    if target is not None:
        line = line.replace('10.20.0.15', target).replace('swp1', target)
    out = s.cli(rec.id, line, node, s.token(rec))
    if interpret:
        s.interpret(rec.id, out['seq'], next(x['id'] for x in out['choices'] if x['text'] == c.correct))
    return out

def scoped(s, rec, ident, interpret=False):
    """Run one command over the whole scope the engine needs (all targets / all job servers / all uplink ports)."""
    c = BY_ID[ident]
    need = sorted(s.scope_of(rec, c.probe) or []) if c.probe else []
    if not need or ident == 'ip_link':
        return command(s, rec, ident, interpret)
    out = None
    for i, x in enumerate(need):
        if x.startswith('server-'):
            out = command(s, rec, ident, interpret and i == 0, node=x)
        else:
            out = command(s, rec, ident, interpret and i == 0, target=x)
    return out

def observe_probe(s, rec, probe):
    ident = next(k for k, c in BY_ID.items() if c.probe == probe and k != 'pod_logs')
    return scoped(s, rec, ident)

def evidence(s, rec, after=False):
    for group in CASES[rec.type]['groups']:
        ident = next((k for k in group if k != 'pod_logs' or not after), group[0])
        scoped(s, rec, ident, interpret=not after)
    for probe in (CASES[rec.type].get('bms'),):
        if probe:
            s.incident_observe(rec.id, probe, where(probe))

def diagnose(s, rec):
    evidence(s, rec)
    return s.incident_hypothesis(rec.id, rec.type)

def respond(s, rec):
    entries = fix(s, rec)
    if any(x['result'] == 'refused' for x in entries):
        if rec.type == 'gpu_health':
            s.incident_act(rec.id, 'gpu_repair')
        elif rec.type == 'gpu_oom':
            s.incident_act(rec.id, 'escalate_platform')
            s.advance_time(10)
            s.incident_act(rec.id, 'memory_saving')
        elif rec.type == 'tor_uplink':
            s.incident_act(rec.id, 'escalate_network')
    return entries

def close_out(s, rec):
    for _ in range(15):
        if rec.state == 'monitoring':
            break
        s.advance_time(10)
    if rec.state != 'monitoring':
        raise AssertionError((rec.type, rec.state, rec.timeline[-3:]))
    s.advance_time(10)
    evidence(s, rec, after=True)
    # Base v1 also requires any additional verify probes (same catalog, not duplicated mappings).
    for p in s.content.types[rec.type]['verify']:
        if p in ('ups', 'cooling'):
            s.incident_observe(rec.id, p, where(p))
        elif not any(e['probe'] == p and e['after'] for e in rec.evidence):
            observe_probe(s, rec, p)
    s.incident_verify(rec.id)
    return s.incident_report(rec.id)
