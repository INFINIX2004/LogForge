#!/bin/bash
# stop.sh — suspends the system to save RAM without losing any data
# Kind cluster and all data is PRESERVED. Run start.sh to resume.

CLUSTER="log-system"

echo "🛑 Stopping Log System"

# Kill any port-forwards
echo "  Stopping port-forwards..."
pkill -f "kubectl port-forward" 2>/dev/null || true

# Stop the Kind node container (preserves cluster, frees RAM)
echo "  Stopping Kind cluster containers..."
docker stop ${CLUSTER}-control-plane 2>/dev/null && echo "✓ Cluster suspended" || echo "  (already stopped)"

# Optionally stop Docker itself to free even more RAM
read -p "Stop Docker too? (frees more RAM but takes longer to start next time) [y/N]: " answer
if [[ "$answer" =~ ^[Yy]$ ]]; then
  echo "  Stopping Docker..."
  sudo systemctl stop docker
  echo "✓ Docker stopped"
  echo ""
  echo "⚠️  To start next time:"
  echo "   sudo systemctl start docker"
  echo "   ./start.sh"
else
  echo ""
  echo "✅ System suspended. Docker still running."
  echo "   To resume: ./start.sh"
fi
