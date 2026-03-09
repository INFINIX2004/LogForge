#!/bin/bash
# deploy.sh — builds images, loads into Kind, applies all k8s manifests
set -e

export DOCKER_DEFAULT_PLATFORM=linux/amd64

CLUSTER="log-system"
NAMESPACE="log-system"

echo "🚀 Deploying Log System to Kubernetes"
echo "   Cluster   : $CLUSTER"
echo "   Namespace : $NAMESPACE"
echo ""

# ── 0. Ensure Kind cluster exists with correct port mappings ──
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER}$"; then
  echo "📦 Creating Kind cluster with port mappings..."
  kind create cluster --config k8s/kind-config.yaml
  echo "✓ Cluster created"
else
  echo "✓ Cluster already exists"
fi
echo ""

# ── 1. Build images ──
echo "📦 Building Docker images..."
docker build -t log-system-collector:latest        ./collector
docker build -t log-system-processor:latest        ./processor
docker build -t log-system-api:latest              ./api
docker build -t log-system-anomaly_detector:latest ./anomaly_detector
# Grafana with ClickHouse plugin baked in — avoids runtime internet download
docker build -t log-system-grafana:latest          ./grafana
echo "✓ Images built"

# ── 2. Load local images into Kind ──
echo ""
echo "📤 Loading local images into Kind cluster..."
for IMAGE in \
  "log-system-collector:latest" \
  "log-system-processor:latest" \
  "log-system-api:latest" \
  "log-system-anomaly_detector:latest" \
  "log-system-grafana:latest"
do
  echo "  Loading $IMAGE..."
  kind load docker-image $IMAGE --name $CLUSTER
done
echo "✓ Local images loaded into Kind"

# ── 3. Load third-party images into Kind ──
# Uses docker save | ctr import with --platform=linux/amd64 to avoid the
# well-known Kind bug where ctr import --all-platforms fails with
# "content digest not found" on multi-arch images (redis, busybox, etc).
echo ""
echo "📦 Loading third-party images into Kind..."

THIRD_PARTY_IMAGES=(
  "clickhouse/clickhouse-server:23.8"
  "redis:7-alpine"
  "busybox:1.36"
  "registry.k8s.io/ingress-nginx/controller:v1.10.0"
  "registry.k8s.io/ingress-nginx/kube-webhook-certgen:v1.4.0"
)

for IMAGE in "${THIRD_PARTY_IMAGES[@]}"; do
  echo "  Preparing $IMAGE..."

  docker image rm -f "$IMAGE" >/dev/null 2>&1 || true
  docker image prune -f >/dev/null 2>&1 || true
  docker pull --platform linux/amd64 "$IMAGE"

  echo "  Loading $IMAGE into Kind..."
  docker save "$IMAGE" | docker exec -i "${CLUSTER}-control-plane" \
    ctr -n k8s.io images import --platform=linux/amd64 --snapshotter=overlayfs -

done

echo "✓ Third-party images loaded"

# ── 4. Install nginx ingress controller ──
echo ""
echo "🌐 Installing Nginx Ingress Controller..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

echo "  Waiting for ingress controller to be ready..."
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

echo "✓ Ingress controller ready"

# ── 5. Apply manifests in order ──
echo ""
echo "📋 Applying Kubernetes manifests..."

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/clickhouse/init-configmap.yaml
kubectl apply -f k8s/storage/pvc.yaml
kubectl apply -f k8s/grafana/grafana-provisioning-configmap.yaml

# Grafana dashboard from JSON file
kubectl create configmap grafana-dashboards \
  --from-file=log-observability.json=grafana/dashboards/log-observability.json \
  --namespace=$NAMESPACE \
  --dry-run=client -o yaml | kubectl apply -f -

# Stateful services first
kubectl apply -f k8s/clickhouse/clickhouse.yaml
kubectl apply -f k8s/redis/redis.yaml

echo "  Waiting for ClickHouse to be ready..."
kubectl wait --namespace $NAMESPACE \
  --for=condition=ready pod \
  --selector=app=clickhouse \
  --timeout=180s

echo "  ✓ ClickHouse ready"

echo "  Waiting for Redis to be ready..."
kubectl wait --namespace $NAMESPACE \
  --for=condition=ready pod \
  --selector=app=redis \
  --timeout=60s

echo "  ✓ Redis ready"

# Application services
kubectl apply -f k8s/collector/collector.yaml
kubectl apply -f k8s/processor/processor.yaml
kubectl apply -f k8s/api/api.yaml
kubectl apply -f k8s/anomaly-detector/anomaly-detector.yaml
kubectl apply -f k8s/grafana/grafana.yaml

# Ingress last
kubectl apply -f k8s/ingress.yaml

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Pod status:"
kubectl get pods -n $NAMESPACE

echo ""
echo "🌐 Access your services:"
echo "   Grafana   : http://localhost:3000/grafana (port-forward) — run start.sh"
echo "   API       : http://localhost/api/health"
echo "   Collector : POST http://localhost/logs"
echo ""
echo "💡 To watch pods come up:"
echo "   kubectl get pods -n log-system -w"
