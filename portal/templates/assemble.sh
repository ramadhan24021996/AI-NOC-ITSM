#!/usr/bin/env bash
# ==============================================================================
# Enterprise Template Assembler — Mega Kreasi Tech NOC IT AI
# Compiles domain modules, layouts, and components into production index.html
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="$DIR/index.html"
BACKUP_DIR="$DIR/backup_trash"

echo "[ASSEMBLER] Starting Enterprise Domain Template Assembly..."
mkdir -p "$BACKUP_DIR"

# Step 1: Create timestamped backup of current index.html before building
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
if [ -f "$OUTPUT_FILE" ]; then
    cp -p "$OUTPUT_FILE" "$BACKUP_DIR/index.html.bak_${TIMESTAMP}"
fi

# Step 2: Build index.html from modular submodules
{
    echo "<!DOCTYPE html>"
    echo "<html lang=\"id\">"
    echo ""
    echo "<head>"
    cat "$DIR/layouts/head.html"
    echo "</head>"
    echo ""
    echo "<body>"
    echo ""
    echo "  <!-- ==================================================="
    echo "     1. SPLASH & LOGIN OVERLAY MODULE"
    echo "  =================================================== -->"
    cat "$DIR/layouts/login_overlay.html"
    echo ""
    echo "  <!-- ==================================================="
    echo "     2. REUSABLE UI MODALS & TOAST NOTIFICATIONS"
    echo "  =================================================== -->"
    cat "$DIR/components/c-toast_notifications.html"
    echo ""
    echo "  <!-- ==================================================="
    echo "     3. MASTER DASHBOARD SHELL"
    echo "  =================================================== -->"
    echo "  <div class=\"shell\">"
    echo ""
    echo "    <!-- SIDEBAR NAVIGATION MODULE -->"
    cat "$DIR/layouts/sidebar.html"
    echo ""
    echo "    <!-- CONTENT WRAPPER -->"
    echo "    <div class=\"content\">"
    echo ""
    echo "      <!-- TOPBAR HEADER MODULE -->"
    cat "$DIR/layouts/header.html"
    echo ""
    echo "      <!-- ========== MAIN PANELS CONTAINER ========== -->"
    echo "      <div class=\"main\" id=\"main-content\">"
    echo ""
    
    # ── Domain 1: Overview & Executive Analytics ─────────────────────────────
    echo "        <!-- DOMAIN 1: OVERVIEW & EXECUTIVE ANALYTICS -->"
    cat "$DIR/modules/1_overview/overview.html"
    echo ""
    for f in "$DIR/modules/1_overview"/*.html; do
        fname=$(basename "$f")
        if [ "$fname" != "overview.html" ]; then
            echo "        <!-- [1_overview] $fname -->"
            cat "$f"
            echo ""
        fi
    done

    # ── Domain 2: Fleet & Infrastructure Health ──────────────────────────────
    echo "        <!-- DOMAIN 2: FLEET & INFRASTRUCTURE HEALTH -->"
    for f in "$DIR/modules/2_fleet_health"/*.html; do
        fname=$(basename "$f")
        echo "        <!-- [2_fleet_health] $fname -->"
        cat "$f"
        echo ""
    done

    # ── Domain 3: Incident & RCA Engine ──────────────────────────────────────
    echo "        <!-- DOMAIN 3: INCIDENT & RCA ENGINE -->"
    for f in "$DIR/modules/3_incident_rca"/*.html; do
        fname=$(basename "$f")
        echo "        <!-- [3_incident_rca] $fname -->"
        cat "$f"
        echo ""
    done

    # ── Domain 4: AI Lifecycle, Training & Voice ─────────────────────────────
    echo "        <!-- DOMAIN 4: AI LIFECYCLE, TRAINING & VOICE -->"
    for f in "$DIR/modules/4_ai_lifecycle"/*.html; do
        fname=$(basename "$f")
        echo "        <!-- [4_ai_lifecycle] $fname -->"
        cat "$f"
        echo ""
    done

    # ── Domain 5: Security, Policy & Governance ──────────────────────────────
    echo "        <!-- DOMAIN 5: SECURITY, POLICY & GOVERNANCE -->"
    for f in "$DIR/modules/5_security_governance"/*.html; do
        fname=$(basename "$f")
        echo "        <!-- [5_security_governance] $fname -->"
        cat "$f"
        echo ""
    done

    # ── Domain 6: Telemetry Stream & Realtime Broker ─────────────────────────
    echo "        <!-- DOMAIN 6: TELEMETRY STREAM & REALTIME BROKER -->"
    for f in "$DIR/modules/6_telemetry_stream"/*.html; do
        fname=$(basename "$f")
        echo "        <!-- [6_telemetry_stream] $fname -->"
        cat "$f"
        echo ""
    done

    echo "      </div><!-- /main-content -->"
    echo "    </div><!-- /content -->"
    echo "  </div><!-- /shell -->"
    echo ""
    echo "  <!-- ==================================================="
    echo "     4. REMOTE ACCESS & SYSTEM CONFIG MODALS"
    echo "  =================================================== -->"
    cat "$DIR/components/c-modal_remote.html"
    echo ""
    echo "  <!-- ==================================================="
    echo "     5. PRODUCTION JAVASCRIPT PIPELINE"
    echo "  =================================================== -->"
    cat "$DIR/layouts/scripts.html"
    echo "</body>"
    echo "</html>"
} > "$OUTPUT_FILE.tmp"

mv "$OUTPUT_FILE.tmp" "$OUTPUT_FILE"

echo "[ASSEMBLER] ✅ Enterprise Domain Assembly SUCCESS!"
echo "[ASSEMBLER] Output file: $OUTPUT_FILE ($(wc -c < "$OUTPUT_FILE") bytes, $(wc -l < "$OUTPUT_FILE") lines)"
