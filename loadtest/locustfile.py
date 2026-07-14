"""Baseline load test — GET endpoints only (no LLM/write traffic).

Run headless, e.g.:
  locust -f loadtest/locustfile.py --host https://adversarialci-api.onrender.com \
    --headless -u 10 -r 2 -t 60s --csv loadtest/results/baseline_10u

Re-run with the same flags after backend changes to compare.
"""
from locust import HttpUser, task, between

REPORT_ID = "buyer_report_20260714_145440"


class DashboardUser(HttpUser):
    # A user browsing the dashboard: mostly reads, weighted like real usage.
    wait_time = between(1, 3)

    @task(3)
    def sessions(self):
        self.client.get("/api/sessions?days=30&limit=20&offset=0", name="/api/sessions")

    @task(2)
    def trends(self):
        self.client.get("/api/sessions/trends?days=30", name="/api/sessions/trends")

    @task(3)
    def vendors_enriched(self):
        self.client.get("/api/vendors/database/enriched", name="/api/vendors/{v}/enriched")

    @task(1)
    def report(self):
        self.client.get(f"/api/reports/{REPORT_ID}", name="/api/reports/{id}")

    @task(1)
    def health(self):
        self.client.get("/health")
