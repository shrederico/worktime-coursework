# Учебные кластеры

Compose, Swarm и Kubernetes запускают одно приложение в независимых стендах.
Все узлы размещены на одном Mac; базы данных стендов раздельные.
Перед запуском кластеров выполните запуск Compose из README: он подготавливает
`.env` и образ `worktime:local`. Требуются запущенный Docker Desktop и Python 3.

## Docker Swarm

```sh
python3 scripts/swarm_lab.py
```

Скрипт создаёт manager и worker проекта `worktime-swarm-lab`. У каждого узла
собственный Docker Engine внутри контейнера `docker:dind`. Основной Docker Engine
не переводится в Swarm. Вложенные узлы используют privileged-режим; сокет Docker
компьютера внутрь не монтируется, управляющий TCP-порт не публикуется.

Приложение доступно на http://localhost:8081, Grafana — на http://localhost:3001.

```sh
docker compose -f infra/swarm/lab.yaml exec -T manager docker node ls
docker compose -f infra/swarm/lab.yaml exec -T manager docker stack services worktime
docker compose -f infra/swarm/lab.yaml exec -T manager docker service ps worktime_app
```

Две реплики приложения ограничены одной на узел. На двух узлах третья реплика
не сможет разместиться при таком ограничении. База и мониторинг закреплены
на узле с меткой `worktime.data=true` из-за локального хранения.

Вложенный стенд использует `APP_MEMORY_LIMIT=0` из-за ограничений cgroup Docker
Desktop. В основной конфигурации Swarm сохранён лимит 512M. Конфигурации Nginx
и мониторинга получают имена с версией по хешу содержимого.

Ручная проверка доставки новой версии:

```sh
python3 scripts/local_pipeline.py
```

Процесс собирает образ, выполняет тесты PostgreSQL, загружает образ на оба узла,
последовательно обновляет две реплики и проверяет результат. Используется
`stop-first`: один экземпляр останавливается перед запуском замены, второй продолжает работать.

## Kubernetes

Требуются `kubectl` в PATH и исполняемый файл kind в `.lab/bin/kind`.
Установка kind описана в [официальной инструкции](https://kind.sigs.k8s.io/docs/user/quick-start/).
Скрипт не устанавливает эти утилиты автоматически. Образы PostgreSQL, Nginx,
Prometheus и Grafana должны быть загружены запуском основной платформы.

```sh
bash scripts/kubernetes_lab.sh
export KUBECONFIG="$PWD/.lab/kubeconfig"
kubectl get nodes
kubectl -n worktime get pods -o wide
kubectl -n worktime port-forward service/proxy 8082:80
```

Последняя команда работает до её остановки; приложение доступно на
http://localhost:8082. Для Grafana в другом терминале:

```sh
export KUBECONFIG="$PWD/.lab/kubeconfig"
kubectl -n worktime port-forward service/grafana 3002:3000
```

Кластер включает control-plane и два worker. Приложение запускается в двух
репликах Deployment, миграции выполняет отдельный Job. PostgreSQL использует PVC;
локальное хранилище kind не переносится автоматически при отказе узла.
История мониторинга временная, панель Grafana восстанавливается из ConfigMap.
Отдельный kubeconfig позволяет не менять основной пользовательский контекст.

## Автоматическая доставка

GitHub Actions обновляет только Swarm через runner на Mac. Используются
переменные репозитория `DEPLOY_ENABLED` и `WORKTIME_RUNTIME_DIR`; параметры
платформы читаются из локального `.env`. Secret `DEPLOY_ENV` текущий workflow
не использует. Настройка и результат запуска: [GITHUB.md](GITHUB.md).

## Ограничения

Отказ физического Mac останавливает все логические узлы. В каждом стенде база
работает в единственном экземпляре. Две реплики приложения не обеспечивают
отказоустойчивость базы и управляющего узла Swarm. Протоколы проверок перечислены
в [VERIFICATION.md](VERIFICATION.md).
