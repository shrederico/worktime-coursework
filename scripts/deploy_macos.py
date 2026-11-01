"""Получает проверенный образ из GHCR и обновляет локальный учебный Swarm."""
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.request import urlopen


def main():
    runtime = Path(os.environ['WORKTIME_RUNTIME_DIR']).resolve()
    image = os.environ['APP_IMAGE']
    if not re.fullmatch(r'ghcr\.io/[a-z0-9._/-]+:[a-f0-9]{40}', image):
        raise SystemExit('Ожидается GHCR-образ с тегом SHA коммита.')
    if not (runtime / '.env').is_file():
        raise SystemExit('В WORKTIME_RUNTIME_DIR отсутствуют локальные настройки .env.')
    lab = ['docker', 'compose', '-f', str(runtime / 'infra/swarm/lab.yaml')]

    def run(*args, **kw):
        return subprocess.run(args, check=True, **kw)

    def output(*args):
        return subprocess.check_output(args, text=True).strip()

    def node(*args):
        return output(*lab, 'exec', '-T', 'manager', 'docker', *args)

    run('docker', 'pull', image)
    archive = runtime / '.lab/github-update.tar'
    try:
        run('docker', 'save', '--platform', 'linux/arm64', '-o', str(archive), image)
        for name in ('manager', 'worker'):
            with archive.open('rb') as file:
                run(*lab, 'exec', '-T', name, 'docker', 'load', stdin=file, stdout=subprocess.DEVNULL)
    finally:
        archive.unlink(missing_ok=True)
    # Секреты уже существуют на стенде; они не загружаются в GitHub.
    node('run', '--rm', '--network', 'worktime_data', '--env-file', '/lab/.env',
         '-e', 'DB_HOST=db', image, 'python', 'manage.py', 'migrate', '--noinput')
    node('service', 'update', '--detach', '--no-resolve-image', '--update-order',
         'stop-first', '--image', image, 'worktime_app')
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        service = json.loads(node('service', 'inspect', 'worktime_app'))[0]
        state = service.get('UpdateStatus', {}).get('State')
        if state in ('paused', 'rollback_started', 'rollback_paused', 'rollback_completed'):
            raise SystemExit(f'Обновление не удалось: {state}')
        ids = node('service', 'ps', '--filter', 'desired-state=running', '-q', 'worktime_app').split()
        tasks = json.loads(node('inspect', *ids)) if ids else []
        if state == 'completed' and len(tasks) == 2 and all(
            t['Status']['State'] == 'running' and t['Spec']['ContainerSpec']['Image'] == image for t in tasks):
            with urlopen('http://127.0.0.1:8081/health/', timeout=10) as response:
                assert json.load(response) == {'status': 'ok'}
            print('GitHub: новая версия работает на обеих репликах Swarm.')
            return
        time.sleep(5)
    raise SystemExit('Превышено время ожидания обновления.')


if __name__ == '__main__':
    main()
