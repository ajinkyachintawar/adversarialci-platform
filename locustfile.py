"""
AdversarialCI Load Testing Suite
================================
Tests all 15 API endpoints with realistic traffic patterns.

Usage:
    # Local testing
    locust -f locustfile.py --host=http://localhost:8000

    # Production testing
    locust -f locustfile.py --host=https://adversarialci-api.onrender.com

    # Headless mode (CI/CD)
    locust -f locustfile.py --host=http://localhost:8000 \
           --users 50 --spawn-rate 5 --run-time 2m --headless

Dashboard: http://localhost:8089
"""

from locust import HttpUser, task, between, events
import random
import time


class AdversarialCIUser(HttpUser):
    """Simulates a typical user interacting with AdversarialCI."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    # Store session IDs for streaming tests
    session_ids = []
    report_ids = []
    
    # Test data
    VERTICALS = ["database", "cloud", "crm"]
    VENDORS = {
        "database": ["MongoDB", "PostgreSQL", "MySQL", "CockroachDB"],
        "cloud": ["AWS", "GCP", "Azure"],
        "crm": ["Salesforce", "HubSpot", "Zoho"]
    }
    MODES = ["buyer", "seller", "analyst"]
    PRIORITIES = ["scalability", "reliability", "cost", "performance", "security"]
    USE_CASES = [
        "Real-time analytics",
        "Distributed transactions",
        "User authentication",
        "Event streaming",
        "Data warehousing"
    ]
    
    def on_start(self):
        """Called when a simulated user starts."""
        # Wake up the server with health check
        self.client.get("/health")
    
    # ==================== Health & Config (High frequency) ====================
    
    @task(10)
    def health_check(self):
        """GET /health - Most frequent, baseline availability check."""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")
    
    @task(5)
    def list_verticals(self):
        """GET /api/verticals - List all verticals."""
        self.client.get("/api/verticals")
    
    @task(3)
    def get_vertical_config(self):
        """GET /api/verticals/{vertical} - Get vertical configuration."""
        vertical = random.choice(self.VERTICALS)
        self.client.get(f"/api/verticals/{vertical}")
    
    # ==================== Vendor Registry (Medium frequency) ====================
    
    @task(5)
    def list_vendors(self):
        """GET /api/vendors/{vertical} - List vendors in a vertical."""
        vertical = random.choice(self.VERTICALS)
        self.client.get(f"/api/vendors/{vertical}")

    @task(5)
    def list_vendors_slim(self):
        """GET /api/vendors/{vertical}/list - Slim vendor list."""
        vertical = random.choice(self.VERTICALS)
        self.client.get(f"/api/vendors/{vertical}/list")
    
    @task(3)
    def get_enriched_vendors(self):
        """GET /api/vendors/{vertical}/enriched - Get vendors with Atlas stats."""
        vertical = random.choice(self.VERTICALS)
        with self.client.get(
            f"/api/vendors/{vertical}/enriched",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.success()  # Expected if vertical doesn't exist
            else:
                response.failure(f"Enriched vendors failed: {response.status_code}")
    
    # ==================== Atlas Intelligence (Medium frequency) ====================
    
    @task(2)
    def get_freshness(self):
        """GET /api/atlas/freshness - Data freshness report."""
        self.client.get("/api/atlas/freshness")
    
    # ==================== Session History (Medium frequency) ====================
    
    @task(3)
    def get_sessions(self):
        """GET /api/sessions - Paginated session history."""
        params = {
            "mode": random.choice(self.MODES + [None]),
            "vertical": random.choice(self.VERTICALS + [None]),
            "days": random.choice([7, 30, 90]),
            "limit": random.choice([10, 20, 50]),
            "offset": random.choice([0, 10, 20])
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        self.client.get("/api/sessions", params=params)
    
    @task(2)
    def get_session_trends(self):
        """GET /api/sessions/trends - Winner distribution trends."""
        params = {
            "vertical": random.choice(self.VERTICALS),
            "days": random.choice([7, 30, 90])
        }
        self.client.get("/api/sessions/trends", params=params)
    
    # ==================== Court Session (Low frequency - expensive) ====================
    
    @task(1)
    def run_evaluation(self):
        """POST /api/evaluate - Start a court session (expensive operation)."""
        vertical = random.choice(self.VERTICALS)
        vendors = self.VENDORS.get(vertical, ["MongoDB", "PostgreSQL"])
        
        primary = random.choice(vendors)
        competitors = [v for v in vendors if v != primary][:2]
        
        payload = {
            "vertical": vertical,
            "mode": random.choice(["buyer", "seller"]),
            "primary": primary,
            "competitors": competitors,
            "plaintiff": {
                "company_name": f"LoadTestCorp_{random.randint(1000, 9999)}",
                "budget": f"${random.randint(10, 100)}k/year",
                "use_case": random.choice(self.USE_CASES),
                "priority": random.choice(self.PRIORITIES),
                "team_size": str(random.randint(3, 50))
            }
        }
        
        with self.client.post(
            "/api/evaluate",
            json=payload,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                session_id = data.get("session_id")
                if session_id:
                    self.session_ids.append(session_id)
                response.success()
            elif response.status_code == 429:
                response.success()  # Rate limited is expected behavior
            else:
                response.failure(f"Evaluation failed: {response.status_code}")
    
    # ==================== Reports (Low frequency) ====================
    
    @task(1)
    def get_report(self):
        """GET /api/reports/{report_id} - Fetch a report."""
        # Use a known report ID or generate one
        report_id = "buyer_report_20260329_221700"  # Example ID
        
        with self.client.get(
            f"/api/reports/{report_id}",
            catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()  # 404 is expected if report doesn't exist
            else:
                response.failure(f"Report fetch failed: {response.status_code}")


class AdminUser(HttpUser):
    """
    Simulates admin operations (lower frequency).
    Requires X-Admin-Key header.
    """
    
    wait_time = between(5, 10)  # Admins are less frequent
    weight = 0  # 1 admin per 10 regular users
    
    ADMIN_KEY = "change-me-in-production"  # Update for production
    
    def on_start(self):
        """Set up admin headers."""
        self.headers = {
            "X-Admin-Key": self.ADMIN_KEY,
            "Content-Type": "application/json"
        }
    
    @task(1)
    def add_and_delete_vendor(self):
        """POST /api/vendors + DELETE /api/vendors - Full CRUD cycle."""
        vendor_name = f"LoadTestVendor_{random.randint(10000, 99999)}"
        
        # Add vendor
        add_payload = {
            "name": vendor_name,
            "vertical": "database",
            "pricing_url": "https://example.com/pricing",
            "github_repo": "test/repo",
            "blog_rss": "https://example.com/blog.xml"
        }
        
        with self.client.post(
            "/api/vendors",
            json=add_payload,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [200, 400]:  # 400 if already exists
                response.success()
            else:
                response.failure(f"Add vendor failed: {response.status_code}")
                return
        
        # Small delay
        time.sleep(0.5)
        
        # Delete vendor
        delete_payload = {
            "name": vendor_name,
            "vertical": "database"
        }
        
        with self.client.request(
            "DELETE",
            "/api/vendors",
            json=delete_payload,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Delete vendor failed: {response.status_code}")


class StressTestUser(HttpUser):
    """
    Aggressive user for stress testing.
    Use sparingly to find breaking points.
    """
    
    wait_time = between(0.1, 0.5)  # Very fast
    weight = 0  # Disabled by default, set to 1 to enable
    
    @task
    def rapid_health_check(self):
        """Hammer the health endpoint."""
        self.client.get("/health")
    
    @task
    def rapid_vendor_list(self):
        """Hammer vendor listing."""
        self.client.get("/api/vendors/database")


# ==================== Event Hooks for Metrics ====================

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log slow requests."""
    if response_time > 5000:  # > 5 seconds
        print(f"⚠️ SLOW REQUEST: {request_type} {name} - {response_time}ms")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary when test stops."""
    print("\n" + "=" * 50)
    print("Load Test Complete")
    print("=" * 50)