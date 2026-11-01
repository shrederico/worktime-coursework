"""Локальный процесс build → test → deploy для учебного Swarm.

Запускается вручную. Автоматический запуск по push предусмотрен отдельно в GitHub Actions.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from urllib.request import urlopen
from swarm_lab import run, node, LAB, ROOT, wait, ready


def main():
    image = 'worktime:build-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    run('docker', 'build', '-t', image, '.')
    run('docker', 'run', '--rm', '--network', 'worktime_data', '--env-file', '.env',
        '-e', 'DB_HOST=db', image, 'python', 'manage.py', 'test', 'tracker')
    archive = ROOT / '.lab/update.tar'
    run('docker', 'save', '-o', str(archive), image)
    try:
        for name in ('manager', 'worker'):
            with archive.open('rb') as file:
                run(*LAB, 'exec', '-T', name, 'docker', 'load', stdin=file, stdout=subprocess.DEVNULL)
    finally:
        archive.unlink(missing_ok=True)
    previous = json.loads(node('manager', 'service', 'inspect', 'worktime_app'))[0]['Spec']['TaskTemplate']['ContainerSpec']['Image']
    node('manager', 'service', 'update', '--detach', '--no-resolve-image',
         '--update-order', 'stop-first', '--image', image, 'worktime_app')

    def updated():
        service = json.loads(node('manager', 'service', 'inspect', 'worktime_app'))[0]
        return (ready() and service.get('UpdateStatus', {}).get('State') == 'completed'
                and service['Spec']['TaskTemplate']['ContainerSpec']['Image'] == image)

    wait(updated, 'Новая версия развёрнута', 240)
    with urlopen('http://127.0.0.1:8081/health/', timeout=10) as response:
        assert json.load(response) == {'status': 'ok'}
    evidence = {'status': 'passed', 'finished_at': datetime.now(timezone.utc).isoformat(),
                'trigger': 'manual local run', 'previous_image': previous, 'image': image,
                'stages': ['build', '15 tests with PostgreSQL', 'load to both nodes', 'rolling update', 'health'],
                'tasks': node('manager', 'service', 'ps', '--filter', 'desired-state=running', 'worktime_app')}
    (ROOT / 'docs/local-pipeline-results.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
