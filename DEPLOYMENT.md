# Deployment Guide

## Docker Compose

```bash
docker-compose up --build
docker-compose down          # stop (data persists)
docker-compose down -v       # stop + wipe all data
```

**Endpoints:** Collector `localhost:8080` · API `localhost:8000` · Grafana `localhost:3001`

---

## Kubernetes (Kind)

### Prerequisites
```bash
# Install Kind
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.22.0/kind-linux-amd64
chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/kubectl
```

### Deploy
```bash
kind create cluster --name log-system
chmod +x k8s/deploy.sh
./k8s/deploy.sh
```

The deploy script handles everything: builds images, loads them into Kind (no internet required), installs ingress, and applies all manifests in the correct order.

**Endpoints:** Grafana `localhost/grafana` · API `localhost/api` · Collector `localhost/logs`

### Monitor
```bash
kubectl get pods -n log-system -w
kubectl logs -n log-system -l app=anomaly-detector -f
```

### Cleanup
```bash
kind delete cluster --name log-system
```

> **Note:** Kind clusters don't survive system reboots. Rerun `kind create cluster` and `./k8s/deploy.sh` after restart.

---

## Troubleshooting

**Pods stuck in ImagePullBackOff** — Kind has no internet access. Load images manually:
```bash
docker pull <image>
docker save <image> | docker exec -i log-system-control-plane ctr -n k8s.io images import -
```

**ClickHouse not ready** — wait 30–60 seconds, it's a heavy image. Check: `kubectl logs -n log-system -l app=clickhouse`

**Anomaly detector not detecting** — needs ~20 data points per service. Run `python scripts/generate_logs.py` first to build baseline history.

**Models retraining from scratch** — don't run `docker-compose down -v` or `kind delete cluster` if you want to keep trained models. Use `docker-compose down` (no `-v`) to preserve volumes.
