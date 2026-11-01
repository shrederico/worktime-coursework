#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -f .env
kubectl create namespace worktime --dry-run=client -o yaml | kubectl apply -f -
kubectl -n worktime create secret generic worktime-env --from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -
kubectl -n worktime create configmap nginx --from-file=default.conf=infra/nginx.conf --dry-run=client -o yaml | kubectl apply -f -
kubectl -n worktime create configmap prometheus --from-file=prometheus.yml=infra/prometheus.yml --dry-run=client -o yaml | kubectl apply -f -
kubectl -n worktime create configmap grafana-datasource --from-file=main.yaml=infra/grafana/provisioning/datasources/main.yaml --dry-run=client -o yaml | kubectl apply -f -
kubectl -n worktime create configmap grafana-provider --from-file=main.yaml=infra/grafana/provisioning/dashboards/main.yaml --dry-run=client -o yaml | kubectl apply -f -
kubectl -n worktime create configmap grafana-dashboard --from-file=worktime.json=infra/grafana/dashboards/worktime.json --dry-run=client -o yaml | kubectl apply -f -
python3 scripts/render_kubernetes.py platform | kubectl apply -f -
kubectl -n worktime rollout status deployment/db --timeout=180s
kubectl -n worktime delete job migrate --ignore-not-found
python3 scripts/render_kubernetes.py migrate | kubectl apply -f -
kubectl -n worktime wait --for=condition=complete job/migrate --timeout=180s
# Изменение Secret/ConfigMap само по себе не перезапускает Pod.
kubectl -n worktime rollout restart deployment/app deployment/proxy deployment/prometheus deployment/grafana
for service in app proxy prometheus grafana; do
  kubectl -n worktime rollout status "deployment/$service" --timeout=180s
done
kubectl -n worktime get pods -o wide
printf '\nДля открытия: kubectl -n worktime port-forward service/proxy 8082:80\n'
