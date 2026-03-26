#!/bin/bash
# ================================================
#   NEPSE Azure Container Auto-Scaling Manager
#   Usage: ./scale-containers.sh [up|down]
# ================================================

set -e

RESOURCE_GROUP="rg-nepse-trading"
APP_NAME="nepse-api"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

show_usage() {
    echo "Usage: $0 [up|down]"
    echo ""
    echo "Commands:"
    echo "  up    - Scale UP for market hours (1.0 CPU + 2.0Gi RAM, min 1 replica)"
    echo "  down  - Scale DOWN for off-hours (0.5 CPU + 1.0Gi RAM, min 0 replicas)"
    echo ""
    echo "Examples:"
    echo "  $0 up     # Scale up before market opens (10 AM Nepal)"
    echo "  $0 down   # Scale down after market closes (3 PM Nepal)"
    exit 1
}

scale_up() {
    echo "================================================"
    echo "   Scaling UP - Market Hours Configuration"
    echo "================================================"
    echo ""
    echo "Target: 1.0 CPU + 2.0Gi RAM + Min 1 Replica"
    echo ""

    az containerapp update \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --cpu 1.0 \
        --memory 2.0Gi \
        --min-replicas 1 \
        --max-replicas 3 \
        --output none

    echo -e "${GREEN}✓ Scaled UP successfully${NC}"
}

scale_down() {
    echo "================================================"
    echo "   Scaling DOWN - Off-Hours Configuration"
    echo "================================================"
    echo ""
    echo "Target: 0.5 CPU + 1.0Gi RAM + Min 0 Replicas"
    echo ""

    az containerapp update \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --cpu 0.5 \
        --memory 1.0Gi \
        --min-replicas 0 \
        --max-replicas 1 \
        --output none

    echo -e "${GREEN}✓ Scaled DOWN successfully${NC}"
    echo ""
    echo -e "${YELLOW}Note: Container will scale to ZERO when idle (saves costs)${NC}"
}

show_status() {
    echo ""
    echo "Current Status:"
    echo "================================================"
    az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "{status:properties.runningStatus, cpu:properties.template.containers[0].resources.cpu, memory:properties.template.containers[0].resources.memory, replicas:properties.template.scale}" \
        -o json
}

# Main logic
if [ $# -eq 0 ]; then
    show_usage
fi

case "$1" in
    up)
        scale_up
        show_status
        ;;
    down)
        scale_down
        show_status
        ;;
    status)
        show_status
        ;;
    *)
        echo -e "${RED}Error: Unknown command '$1'${NC}"
        echo ""
        show_usage
        ;;
esac

echo ""
echo -e "${GREEN}✓ Operation complete!${NC}"
