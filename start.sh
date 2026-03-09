#!/bin/bash
# start.sh — starts the existing Kind cluster and forwards ports
# Run this after system restart. Run deploy.sh only once for initial setup.

CLUSTER="log-system"
NAMESPACE="log-system"

echo "🚀 Starting Log System"

# Check if cluster exists
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER}$"; then
  echo "❌ Cluster not found. Run ./k8s/deploy.sh first to set up the system."
  exit 1
fi

# Set kubectl context
kubectl cluster-info --context kind-${CLUSTER} >/dev/null 2>&1 || {
  echo "❌ Cannot connect to cluster. It may have been deleted. Run ./k8s/deploy.sh"
  exit 1
}

echo "✓ Cluster found"

# Check pod status
echo ""
echo "📊 Pod status:"
kubectl get pods -n $NAMESPACE

# Wait for pods if any are not ready
NOT_READY=$(kubectl get pods -n $NAMESPACE --no-headers | grep -v "1/1" | wc -l)
if [ "$NOT_READY" -gt 0 ]; then
  echo ""
  echo "⏳ Waiting for pods to be ready..."
  kubectl wait --namespace $NAMESPACE \
    --for=condition=ready pod \
    --selector=app=clickhouse \
    --timeout=120s
  kubectl wait --namespace $NAMESPACE \
    --for=condition=ready pod \
    --selector=app=redis \
    --timeout=60s
  echo "✓ Core services ready"
fi

echo ""
echo "✅ System is up!"
echo ""
echo "🌐 Access your services:"
echo "   API health : http://localhost/api/health"
echo "   Logs       : http://localhost/api/logs"
echo "   Collector  : POST http://localhost/logs"
echo ""
echo "📊 Starting Grafana port-forward..."
echo "   Grafana    : http://localhost:3000/grafana (admin/admin)"
echo ""
kubectl port-forward svc/grafana 3000:3000 -n $NAMESPACE
