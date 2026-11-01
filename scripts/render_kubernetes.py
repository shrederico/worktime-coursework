"""Подставляет выбранный образ без изменения исходных YAML и без секретов."""
import os
from pathlib import Path
import re
import sys

if len(sys.argv) != 2 or sys.argv[1] not in ('platform', 'migrate'):
    raise SystemExit('Использование: python3 scripts/render_kubernetes.py platform|migrate')
image = os.getenv('APP_IMAGE', 'worktime:local')
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/:@-]*', image):
    raise SystemExit('APP_IMAGE должен содержать только адрес образа и тег или digest.')
path = Path(__file__).resolve().parent.parent / 'infra/kubernetes' / f'{sys.argv[1]}.yaml'
print(path.read_text().replace('image: worktime:local', f'image: {image}'), end='')
