#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export KUBECONFIG="$PWD/.lab/kubeconfig"
kind_bin="$PWD/.lab/bin/kind"
test -x "$kind_bin" || { printf 'Нет .lab/bin/kind. Установите официальный kind в эту папку.\n'; exit 1; }
if ! "$kind_bin" get clusters | grep -qx worktime; then
  "$kind_bin" create cluster --name worktime --config infra/kubernetes/kind.yaml --kubeconfig "$KUBECONFIG"
fi
# Docker Desktop может хранить индекс нескольких архитектур без всех слоёв.
# Экспорт только архитектуры Mac делает архив совместимым с containerd в kind.
case "$(uname -m)" in
  arm64) image_platform=linux/arm64 ;;
  x86_64) image_platform=linux/amd64 ;;
  *) printf 'Архитектура не поддерживается этим учебным скриптом.\n'; exit 1 ;;
esac
archive="$PWD/.lab/kube-images.tar"
trap 'rm -f "$archive"' EXIT
docker image save --platform "$image_platform" -o "$archive" worktime:local postgres:17-alpine nginx:1.28-alpine prom/prometheus:v3.5.0 grafana/grafana:12.1.1
"$kind_bin" load image-archive "$archive" --name worktime
bash scripts/deploy_kubernetes.sh
