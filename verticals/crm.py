"""
CRM Vertical Configuration (v2)
===============================
Config for CRM platform comparisons.
NOTE: Vendors moved to vendors.json
"""

CRM_CONFIG = {
    "name":         "crm",
    "display_name": "CRM Platforms",
    "description":  "Customer relationship management and sales platforms",
    
    "dimensions": [
        "cost", "ease_of_use", "customization", "integrations",
        "lock_in_risk", "reporting", "scalability", "support"
    ],
    
    "dimension_keywords": {
        "cost": ["price", "pricing", "cost", "expensive", "cheap", "free", "per-seat", "per-user", "tier", "plan", "subscription", "billing", "license", "enterprise", "professional", "tco"],
        "ease_of_use": ["easy", "simple", "intuitive", "complex", "difficult", "user-friendly", "learning curve", "onboarding", "training", "adoption", "ui", "ux", "interface"],
        "customization": ["custom", "customize", "workflow", "automation", "field", "object", "module", "api", "low-code", "no-code", "formula", "process builder", "flow"],
        "integrations": ["integration", "integrate", "connect", "connector", "api", "zapier", "native", "marketplace", "app", "plugin", "sync", "import", "export", "appexchange"],
        "lock_in_risk": ["lock-in", "vendor", "migration", "export", "portable", "data ownership", "switching cost", "proprietary", "open", "exit", "contract"],
        "reporting": ["report", "reporting", "dashboard", "analytics", "insight", "metrics", "kpi", "forecast", "pipeline", "visualization", "chart", "bi"],
        "scalability": ["scale", "scaling", "enterprise", "users", "records", "storage", "performance", "large", "growth", "unlimited", "api limits"],
        "support": ["support", "help", "service", "sla", "response time", "training", "documentation", "community", "partner", "implementation", "consultant"]
    },
    
    "priority_weights": {
        "cost": {"cost": 3.0, "ease_of_use": 2.0, "integrations": 1.5, "lock_in_risk": 1.5, "customization": 1.0, "reporting": 1.0, "scalability": 0.5, "support": 0.5},
        "ease_of_use": {"ease_of_use": 3.0, "support": 2.0, "integrations": 1.5, "cost": 1.5, "customization": 1.0, "reporting": 1.0, "scalability": 0.5, "lock_in_risk": 0.5},
        "customization": {"customization": 3.0, "integrations": 2.5, "scalability": 2.0, "support": 1.5, "ease_of_use": 1.0, "cost": 1.0, "reporting": 1.0, "lock_in_risk": 0.5},
        "enterprise": {"scalability": 3.0, "customization": 2.5, "support": 2.0, "integrations": 1.5, "reporting": 1.5, "lock_in_risk": 1.0, "cost": 0.5, "ease_of_use": 0.5},
        "no-lock-in": {"lock_in_risk": 3.0, "integrations": 2.0, "cost": 1.5, "ease_of_use": 1.5, "customization": 1.0, "reporting": 1.0, "scalability": 1.0, "support": 0.5}
    },
    
    "default_weights": {"cost": 1.5, "ease_of_use": 1.5, "customization": 1.5, "integrations": 1.5, "lock_in_risk": 1.0, "reporting": 1.0, "scalability": 1.0, "support": 1.0},
    
    "judge_context": "competitive CRM platform evaluation",
    
    "tavily_query_templates": [
        "{company} CRM features overview {year}",
        "{company} CRM news announcements {year}",
        "{company} CRM reviews complaints problems {year}",
        "{company} CRM pricing changes {year}"
    ],
    
    "hn_relevance_keywords": [
        "crm", "salesforce", "hubspot", "zoho", "pipedrive", "dynamics", "sales", "customer", "pipeline", "lead",
        "pricing", "per-seat", "cost", "expensive", "integration", "automation", "workflow", "migration", "alternative"
    ],
    
    "migration_query_templates": [
        "why we switched from {company} CRM to alternative",
        "{company} CRM migration case study {year}",
        "left {company} CRM reasons"
    ],
    
    "complaint_query_templates": [
        "{company} CRM pricing complaints expensive {year}",
        "{company} CRM problems issues users {year}",
        "{company} CRM difficult complex"
    ],
    
    "plaintiff_questions": [
        {"key": "company_name", "prompt": "Company name: ", "required": True},
        {"key": "team_size", "prompt": "Sales team size", "example": "10 reps, 2 managers", "required": True},
        {"key": "budget", "prompt": "Monthly CRM budget", "example": "$500", "required": True},
        {"key": "use_case", "prompt": "Primary use case", "example": "B2B sales, inbound leads", "required": True},
        {"key": "deal_volume", "prompt": "Monthly deal volume", "example": "100 deals/month", "required": True},
        {"key": "current_crm", "prompt": "Current CRM (if any)", "required": False},
        {"key": "must_have_integrations", "prompt": "Must-have integrations", "example": "Gmail, Slack", "required": False},
        {"key": "priority", "prompt": "Top priority (cost / ease_of_use / customization / enterprise / no-lock-in)", "required": True}
    ],
    
    "eval_ground_truth": {
        "Salesforce": {"pricing_facts": ["enterprise", "unlimited"], "tech_facts": ["apex", "lightning", "appexchange"], "known_complaints": ["expensive", "complex"]},
        "HubSpot": {"pricing_facts": ["free tier", "starter", "professional"], "tech_facts": ["marketing hub", "sales hub", "workflows"], "known_complaints": ["pricing jumps", "feature gating"]},
        "Zoho CRM": {"pricing_facts": ["free tier"], "tech_facts": ["zoho one", "blueprint"], "known_complaints": ["ui dated", "support"]}
    }
}