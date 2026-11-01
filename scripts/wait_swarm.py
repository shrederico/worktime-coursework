"""Дожидается именно новой версии всех сервисов, а не ответа старой реплики."""
import json
import os
import subprocess
import time


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def main():
    expected = os.environ['APP_IMAGE']
    deadline = time.monotonic() + 240
    services = ['worktime_proxy', 'worktime_app', 'worktime_db', 'worktime_prometheus', 'worktime_grafana']
    while time.monotonic() < deadline:
        ready = True
        for name in services:
            service = json.loads(docker('service', 'inspect', name))[0]
            state = service.get('UpdateStatus', {}).get('State', '')
            if state in ('paused', 'rollback_started', 'rollback_paused', 'rollback_completed'):
                raise SystemExit(f'{name}: обновление не завершено успешно ({state}).')
            image = service['Spec']['TaskTemplate']['ContainerSpec']['Image']
            if name == 'worktime_app' and image.split('@')[0] != expected.split('@')[0]:
                raise SystemExit('Сервис app настроен на другой образ, обновление не подтверждено.')
            desired = service['Spec']['Mode']['Replicated']['Replicas']
            ids = docker('service', 'ps', '--filter', 'desired-state=running', '-q', name).split()
            tasks = json.loads(docker('inspect', *ids)) if ids else []
            # Проверяем не только число контейнеров, но и образ каждой реплики.
            running = [task for task in tasks if task['Status']['State'] == 'running'
                       and task['Spec']['ContainerSpec']['Image'] == image]
            if len(running) != desired or state not in ('', 'completed'):
                ready = False
        if ready:
            print('Все сервисы запущены; реплики приложения используют новую версию.')
            return
        print('Ожидаем готовность сервисов и завершение обновления…', flush=True)
        time.sleep(5)
    raise SystemExit('Истекло время ожидания кластера. Проверьте docker stack ps worktime --no-trunc.')


if __name__ == '__main__':
    main()
