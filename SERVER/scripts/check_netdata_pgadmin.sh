#!/usr/bin/env bash
# Diagnostic script for Netdata and PostgreSQL/pgAdmin (Bash)
# Usage: sudo bash check_netdata_pgadmin.sh

set -euo pipefail
echo "=== Listening sockets for 19999 (Netdata) and 5432 (Postgres) ==="
if command -v ss > /dev/null; then
  ss -tulpn | grep -E ":19999|:5432" || true
else
  netstat -tulpn | grep -E ":19999|:5432" || true
fi

echo "\n=== Test Netdata HTTP API ==="
if command -v curl > /dev/null; then
  curl -v --max-time 5 http://localhost:19999/api/v1/version || true
else
  echo "curl not found"
fi

echo "\n=== systemd/service check for netdata and postgresql ==="
if command -v systemctl > /dev/null; then
  systemctl status netdata --no-pager || true
  systemctl status postgresql --no-pager || true
fi

echo "\n=== Docker containers (netdata/pgadmin/postgres) ==="
docker ps --format "table {{.ID}}\t{{.Image}}\t{{.Names}}\t{{.Ports}}" | grep -E "netdata|pgadmin|postgres" || true

echo "\n=== Netdata config (bind/listen) ==="
if [ -f /etc/netdata/netdata.conf ]; then
  grep -nE "^\s*bind to|^\s*web port|^\s*memory mode|^\s*enable streaming" -n /etc/netdata/netdata.conf || true
else
  echo "/etc/netdata/netdata.conf not found"
fi

echo "\n=== PostgreSQL config files (pg_hba.conf & postgresql.conf) ==="
POSSIBLE=(/etc/postgresql/*/main/pg_hba.conf /var/lib/pgsql/data/pg_hba.conf /var/lib/postgresql/data/pg_hba.conf)
for f in "${POSSIBLE[@]}"; do
  if [ -f $f ]; then
    echo "--- $f ---"
    sed -n '1,200p' $f || true
  fi
done

# Check listen_addresses
POSS_CONF=(/etc/postgresql/*/main/postgresql.conf /var/lib/pgsql/data/postgresql.conf /var/lib/postgresql/data/postgresql.conf)
for c in "${POSS_CONF[@]}"; do
  if [ -f $c ]; then
    echo "--- $c (listen_addresses & port) ---"
    grep -n "listen_addresses\|port" $c || true
  fi
done

echo "\n=== Quick psql connectivity test (requires psql in PATH) ==="
if command -v psql > /dev/null; then
  psql -h localhost -U postgres -p 5432 -c '\l' || true
else
  echo "psql not found"
fi

echo "\n=== End of Bash diagnostic ==="
