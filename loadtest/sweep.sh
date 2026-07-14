#!/bin/bash
# Single-user latency sweep of all GET endpoints. Run before/after backend changes.
B=${1:-https://adversarialci-api.onrender.com}
for ep in "/api/verticals" "/api/verticals/database" "/api/vendors/database" \
  "/api/vendors/database/list" "/api/vendors/database/enriched" "/api/atlas/freshness" \
  "/api/sessions?days=30&limit=20&offset=0" "/api/sessions/trends?days=30" \
  "/api/reports/buyer_report_20260714_145440" "/health"; do
  t1=$(curl -s -o /dev/null -w "%{time_total}" "$B$ep")
  t2=$(curl -s -o /dev/null -w "%{time_total}" "$B$ep")
  echo "$ep | ${t1}s / ${t2}s"
done
