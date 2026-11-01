"""Отдельный двухузловой Swarm для демонстрации на одном Mac."""
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
LAB = ['docker', 'compose', '-f', 'infra/swarm/lab.yaml']


def run(*args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def output(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def node(name, *args):
    return output(*LAB, 'exec', '-T', name, 'docker', *args)


def wait(check, message, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if check():
                print(message, flush=True)
                return
        except Exception:
            pass
        time.sleep(3)
    raise RuntimeError(message + ': время ожидания истекло')


def ready():
    rows = node('manager', 'service', 'ls', '--format', '{{.Replicas}}').splitlines()
    return len(rows) == 5 and all(x.split()[0].split('/')[0] == x.split()[0].split('/')[1] for x in rows)


def main():
    run(*LAB, 'up', '-d')
    for name in ('manager', 'worker'):
        wait(lambda: node(name, 'info', '--format', '{{.ServerVersion}}'), f'{name}: Docker готов')
    manager_id = output(*LAB, 'ps', '-q', 'manager')
    ip = output('docker', 'inspect', '-f', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', manager_id)
    if node('manager', 'info', '--format', '{{.Swarm.LocalNodeState}}') != 'active':
        node('manager', 'swarm', 'init', '--advertise-addr', ip)
    if node('worker', 'info', '--format', '{{.Swarm.LocalNodeState}}') != 'active':
        token = node('manager', 'swarm', 'join-token', '-q', 'worker')
        # Токен не выводим в журнал.
        node('worker', 'swarm', 'join', '--token', token, f'{ip}:2377')
    manager_node = node('manager', 'info', '--format', '{{.Swarm.NodeID}}')
    node('manager', 'node', 'update', '--label-add', 'worktime.data=true', manager_node)
    cache = ROOT / '.lab'
    cache.mkdir(exist_ok=True)
    images = ['worktime:local', 'postgres:17-alpine', 'nginx:1.28-alpine',
              'prom/prometheus:v3.5.0', 'grafana/grafana:12.1.1']
    archive = cache / 'swarm-images.tar'
    run('docker', 'save', '-o', str(archive), *images)
    for name in ('manager', 'worker'):
        with archive.open('rb') as file:
            run(*LAB, 'exec', '-T', name, 'docker', 'load', stdin=file, stdout=subprocess.DEVNULL)
    archive.unlink()
    run('docker', 'exec', manager_id, 'mkdir', '-p', '/lab')
    run('docker', 'cp', str(ROOT / 'infra'), f'{manager_id}:/lab/infra')
    run('docker', 'cp', str(ROOT / '.env'), f'{manager_id}:/lab/.env')
    version = output('python3', 'scripts/config_version.py')
    run('docker', 'exec', manager_id, 'sh', '-c',
        'set -a; . /lab/.env; set +a; cd /lab; '
        f'export APP_IMAGE=worktime:local APP_MEMORY_LIMIT=0 CONFIG_VERSION={version}; '
        'docker stack deploy --resolve-image never -c infra/swarm/stack.yml worktime')
    for command in ('migrate --noinput', 'seed_demo'):
        def initialize():
            run('docker', 'exec', manager_id, 'docker', 'run', '--rm', '--network', 'worktime_data',
                '--env-file', '/lab/.env', '-e', 'DB_HOST=db', 'worktime:local',
                'python', 'manage.py', *command.split(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            return True
        wait(initialize, f'{command}: выполнено')
    node('manager', 'service', 'update', '--replicas-max-per-node', '1', '--detach', 'worktime_app')
    wait(ready, 'Все пять сервисов готовы', timeout=240)
    with urlopen('http://127.0.0.1:8081/health/', timeout=10) as response:
        assert json.load(response) == {'status': 'ok'}
    evidence = {'nodes': node('manager', 'node', 'ls'),
                'services': node('manager', 'service', 'ls'),
                'app_tasks_before': node('manager', 'service', 'ps', '--filter', 'desired-state=running', 'worktime_app')}
    worker_container = node('worker', 'ps', '-q', '--filter', 'label=com.docker.swarm.service.name=worktime_app')
    assert worker_container, 'На worker не найдена реплика приложения'
    node('worker', 'kill', worker_container)
    wait(lambda: ready() and bool(node('worker', 'ps', '-q', '--filter', 'label=com.docker.swarm.service.name=worktime_app')),
         'Реплика восстановлена после остановки', timeout=180)
    evidence['app_tasks_after'] = node('manager', 'service', 'ps', 'worktime_app')
    evidence['status'] = 'passed'
    (ROOT / 'docs/swarm-results.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    print('Проверка Swarm завершена: http://localhost:8081', flush=True)


if __name__ == '__main__':
    main()
