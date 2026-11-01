"""Проверка Compose: тесты, резервная копия, восстановление и пересоздание БД.

Запуск: python3 scripts/verify_platform.py
На время проверки приложение останавливается, чтобы записи не менялись.
Рабочий том не удаляется. Результаты сохраняются в docs/verification-results.json.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
RESULT = ROOT / 'docs/verification-results.json'
SQL = """SELECT json_build_object(
 'tasks', (SELECT json_agg(t ORDER BY id) FROM tracker_task t),
 'entries', (SELECT json_agg(t ORDER BY id) FROM tracker_timeentry t),
 'users', (SELECT json_agg(t ORDER BY id) FROM
   (SELECT id, username, first_name, last_name, email, is_active, is_staff,
           is_superuser, password, date_joined, last_login FROM auth_user) t)
);"""


def run(*args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def compose(*args, **kwargs):
    return run('docker', 'compose', *args, **kwargs)


def fingerprint(database=None):
    # Содержимое и хеши паролей не печатаются: сравниваем только SHA256 снимка.
    output = compose('exec', '-T', 'db', 'sh', '-c',
        'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "${1:-$POSTGRES_DB}" -At -c "$2"',
        'sh', database or '', SQL, capture_output=True, text=True).stdout
    canonical = json.dumps(json.loads(output), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def database_action(action, name):
    compose('exec', '-T', 'db', 'sh', '-c',
            f'{action} -U "$POSTGRES_USER" "$1"', 'sh', name, capture_output=True)


def main():
    results = {'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'running', 'checks': []}
    paused = False
    created_restore = False
    restore_name = f'worktime_verify_{int(time.time())}_{os.getpid()}'
    failure = None

    def passed(name):
        results['checks'].append({'name': name, 'status': 'passed'})
        print(f'OK: {name}', flush=True)

    try:
        compose('ps', '--quiet', capture_output=True)
        running = set(compose('ps', '--services', '--status', 'running', capture_output=True, text=True).stdout.split())
        required = {'app', 'db', 'proxy', 'prometheus', 'grafana'}
        if not required.issubset(running):
            raise RuntimeError('Сначала запустите все пять сервисов через scripts/start.sh.')
        passed('Пять сервисов запущены')
        compose('exec', '-T', 'app', 'python', 'manage.py', 'test', 'tracker')
        passed('Тесты приложения с PostgreSQL')

        # Останавливаем только приложение этого проекта, не Docker и не другие проекты.
        paused = True
        compose('stop', 'app')
        before = fingerprint()
        backup_dir = ROOT / 'backups'
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / f'verified-{restore_name}.sql'
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as file:
            compose('exec', '-T', 'db', 'sh', '-c',
                    'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"', stdout=file)
        results['backup'] = str(backup.relative_to(ROOT))
        passed('Резервная копия создана при остановленной записи')

        database_action('createdb', restore_name)
        created_restore = True
        with backup.open('rb') as file:
            compose('exec', '-T', 'db', 'sh', '-c',
                    'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1"',
                    'sh', restore_name, stdin=file, stdout=subprocess.DEVNULL)
        if fingerprint(restore_name) != before:
            raise RuntimeError('Содержимое восстановленной базы отличается от исходного.')
        passed('Пользователи, задачи и часы полностью совпадают после восстановления')
        database_action('dropdb', restore_name)
        created_restore = False

        compose('up', '-d', '--no-deps', '--force-recreate', '--wait', '--wait-timeout', '120', 'db')
        if fingerprint() != before:
            raise RuntimeError('Данные изменились после пересоздания контейнера БД.')
        passed('Данные сохранились после пересоздания контейнера БД с тем же томом')
    except (subprocess.SubprocessError, OSError, RuntimeError, ValueError) as error:
        failure = error
        results['error'] = str(error)
    finally:
        if created_restore:
            try:
                database_action('dropdb', restore_name)
            except Exception:
                results['cleanup_warning'] = f'Временная база {restore_name} осталась для диагностики.'
        if paused:
            try:
                compose('up', '-d', '--no-deps', '--wait', '--wait-timeout', '120', 'app')
                # Nginx мог запомнить IP прежнего app: пересоздаём только прокси.
                compose('up', '-d', '--no-deps', '--force-recreate', 'proxy')
                deadline = time.monotonic() + 30
                while True:
                    try:
                        with urlopen('http://127.0.0.1:8080/health/', timeout=5) as response:
                            if json.load(response) != {'status': 'ok'}:
                                raise RuntimeError('Неожиданный ответ health.')
                        break
                    except (OSError, RuntimeError):
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(1)
                passed('Приложение снова доступно после проверки')
            except Exception as error:
                results['restart_error'] = str(error)
                failure = failure or error
        results['status'] = 'failed' if failure else 'passed'
        results['finished_at'] = datetime.now(timezone.utc).isoformat()
        RESULT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    if failure:
        print('Проверка не завершена. Подробности: docs/verification-results.json', file=sys.stderr)
        return 1
    print('Все проверки выполнены. Результаты: docs/verification-results.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
