"""Проверяет узлы, сеть и автоматическую замену Pod приложения."""
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
ENV = {**os.environ, 'KUBECONFIG': str(ROOT / '.lab/kubeconfig')}


def kube(*args):
    return subprocess.check_output(['kubectl', *args], env=ENV, text=True).strip()


def pods():
    return json.loads(kube('-n', 'worktime', 'get', 'pods', '-l', 'app=app', '-o', 'json'))['items']


def main():
    kube('-n', 'worktime', 'rollout', 'status', 'deployment/app', '--timeout=180s')
    before = pods()
    removed = before[0]['metadata']['name']
    old_uid = before[0]['metadata']['uid']
    assert len(before) == 2
    assert len({p['spec']['nodeName'] for p in before}) == 2
    kube('-n', 'worktime', 'delete', 'pod', removed, '--wait=true')
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        after = pods()
        if len(after) == 2 and all(p['metadata']['uid'] != old_uid and
            any(c['type'] == 'Ready' and c['status'] == 'True' for c in p['status'].get('conditions', [])) for p in after):
            break
        time.sleep(3)
    else:
        raise RuntimeError('Не дождались двух готовых реплик после удаления Pod')
    response = kube('-n', 'worktime', 'exec', 'deployment/proxy', '--',
                    'wget', '-qO-', 'http://127.0.0.1/health/')
    assert json.loads(response) == {'status': 'ok'}
    evidence = {'status': 'passed', 'nodes': kube('get', 'nodes', '-o', 'wide'),
                'pods': kube('-n', 'worktime', 'get', 'pods', '-o', 'wide'),
                'deleted_pod': removed, 'replacement_pods': [p['metadata']['name'] for p in after],
                'network': 'Nginx → Django → PostgreSQL: health ok',
                'limitation': 'Логические узлы на одном Mac, единственная база без репликации'}
    (ROOT / 'docs/kubernetes-results.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    print('Kubernetes: сеть и восстановление Pod проверены.')


if __name__ == '__main__':
    main()
