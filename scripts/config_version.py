"""Версия конфигураций Swarm зависит от их содержимого."""
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parent.parent
files = ['infra/nginx.conf', 'infra/prometheus.yml',
         'infra/grafana/provisioning/datasources/main.yaml',
         'infra/grafana/provisioning/dashboards/main.yaml',
         'infra/grafana/dashboards/worktime.json']
digest = hashlib.sha256()
for name in files:
    data = (root / name).read_bytes()
    digest.update(name.encode() + b'\0' + str(len(data)).encode() + b'\0' + data)
print(digest.hexdigest()[:16])
