"""Phase9 rule overlay. Keeps published incident v1 fingerprints and old saves unchanged."""
import hashlib
import json
from copy import deepcopy

RULES = {'gpu_oom': {'escalate_platform': {'result': 'call', 'team': 'platform',
                                         'text': '플랫폼 담당에게 작업 메모리 설정 검토를 요청했습니다.'}},
         'storage_full': {'escalate_platform': {'result': 'call', 'team': 'platform',
                                              'text': '플랫폼 담당에게 안전한 스토리지 확장 승인을 요청했습니다.'}}}
FINGERPRINT = hashlib.sha256(json.dumps(RULES, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class OperatingRules:
    def _tdef(self, rec):
        definition = super()._tdef(rec)
        if rec.type not in RULES:
            return definition
        definition = deepcopy(definition)
        definition['actions'].update(RULES[rec.type])
        return definition
