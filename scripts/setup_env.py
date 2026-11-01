"""Создаёт локальные пароли. Существующий .env никогда не перезаписывается."""
from pathlib import Path
import secrets
import os

target = Path(__file__).resolve().parent.parent / '.env'
if target.exists():
    print('.env уже существует, оставлен без изменений.')
else:
    data = {'SECRET_KEY': secrets.token_hex(32), 'POSTGRES_DB': 'worktime', 'POSTGRES_USER': 'worktime',
            'POSTGRES_PASSWORD': secrets.token_hex(20), 'DEMO_PASSWORD': secrets.token_urlsafe(15),
            'GRAFANA_PASSWORD': secrets.token_urlsafe(15), 'ALLOWED_HOSTS': 'localhost,127.0.0.1,app',
            'CSRF_TRUSTED_ORIGINS': 'http://localhost:8080,http://127.0.0.1:8080'}
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as file:
        file.write('\n'.join(f'{key}={value}' for key, value in data.items()) + '\n')
    print('Создан .env с индивидуальными паролями. Не публикуйте этот файл.')
