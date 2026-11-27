"""A/B operating strategies must differ in the real Python ledger, not in UI wording."""
import unittest
from aidc.incidents.session import IncidentSession
from aidc.incidents.operating_rules import OperatingRules
from tests.incident_support import Temp, start_open, diagnose, fix, finish

PATHS = {
    'dns': (['dns_failover'], ['escalate_network']),
    'tor_uplink': (['reroute_uplink'], ['escalate_network']),
    'congestion': (['qos_adjust'], ['escalate_network']),
    'gpu_health': (['isolate_migrate'], ['gpu_repair']),
    'gpu_oom': (['ask_consent', 'reduce_batch'], ['escalate_platform', '+10', 'memory_saving']),
    'storage_full': (['cleanup_temp'], ['escalate_platform', '+10', 'expand_storage']),
    'storage_latency': (['storage_path'], ['escalate_platform']),
    'crashloop': (['escalate_platform', '+10', 'rollback_deploy'], ['escalate_platform', '+10', 'config_fix']),
}


class Phase9Practice(OperatingRules, IncidentSession):
    """Test the exact production Phase9 rule overlay on isolated individual cases."""


class OperatingBranchesTests(unittest.TestCase):
    def test_eight_legal_ab_paths_change_time_or_resources_and_persist(self):
        temp = Temp()
        self.addCleanup(temp.cleanup)
        for cause, paths in PATHS.items():
            states = []
            for i, path in enumerate(paths):
                with self.subTest(cause=cause, path=i):
                    name = f'{cause}-{i}.db'
                    s = Phase9Practice(temp.db(name), practice=cause, seed=5)
                    s.confirm_shift_briefing()
                    start_open(s)
                    rec = s.incident.records[0]
                    while rec.state == 'armed':
                        s.advance_time(10)
                    diagnose(s, rec)
                    s.incident_act(rec.id, 'notify_customer')
                    entries = fix(s, rec, path)
                    self.assertFalse(any(e['result'] in ('none', 'refused') for e in entries), entries)
                    finish(s, rec)
                    self.assertEqual(rec.state, 'closed')
                    run = s.runs[rec.rid]
                    states.append((rec.recovered, rec.downtime, rec.slow_minutes,
                                   [a.payload() if hasattr(a, 'payload') else str(a) for a in run.server_allocations]))
                    saved = s.db.get_simulation()
                    s.db.close()
                    restored = Phase9Practice(temp.db(name))
                    self.assertEqual(saved, restored.db.get_simulation())
                    self.assertEqual(restored.record(rec.id).state, 'closed')
            self.assertNotEqual(states[0], states[1], cause)


if __name__ == '__main__':
    unittest.main()
