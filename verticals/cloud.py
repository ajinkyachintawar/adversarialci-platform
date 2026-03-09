"""
Cloud Vertical Configuration (v2)
=================================
Config for cloud provider comparisons.
NOTE: Vendors moved to vendors.json
"""

CLOUD_CONFIG = {
    "name":         "cloud",
    "display_name": "Cloud Providers",
    "description":  "Infrastructure-as-a-service and cloud platforms",
    
    "dimensions": [
        "cost", "performance", "scalability", "simplicity",
        "lock_in_risk", "compliance", "global_reach", "support"
    ],
    
    "dimension_keywords": {
        "cost": ["price", "pricing", "cost", "expensive", "cheap", "free tier", "billing", "dollar", "$", "budget", "reserved", "spot", "on-demand", "savings plan", "egress", "data transfer", "tco"],
        "performance": ["latency", "speed", "fast", "slow", "performance", "benchmark", "throughput", "iops", "bandwidth", "compute", "gpu", "cpu", "memory", "nvme", "bare metal"],
        "scalability": ["scale", "scaling", "auto-scale", "elastic", "horizontal", "vertical", "capacity", "load balancer", "kubernetes", "k8s", "container", "serverless", "lambda"],
        "simplicity": ["easy", "simple", "complex", "difficult", "setup", "console", "ui", "ux", "portal", "dashboard", "documentation", "learning curve", "onboarding", "sdk", "cli", "terraform"],
        "lock_in_risk": ["lock-in", "vendor", "migration", "portable", "open source", "proprietary", "multi-cloud", "kubernetes", "terraform", "cloud agnostic", "exit cost", "data export"],
        "compliance": ["gdpr", "hipaa", "soc2", "soc 2", "iso 27001", "fedramp", "pci", "compliance", "certified", "data residency", "sovereignty", "audit", "security", "encryption", "govcloud"],
        "global_reach": ["region", "regions", "availability zone", "az", "edge", "cdn", "points of presence", "pop", "latency", "geographic", "data center", "local zone", "global", "worldwide"],
        "support": ["support", "sla", "uptime", "99.9", "enterprise", "premium", "response time", "tam", "account manager", "professional services", "training"]
    },
    
    "priority_weights": {
        "cost": {"cost": 3.0, "scalability": 2.0, "lock_in_risk": 2.0, "simplicity": 1.5, "performance": 1.0, "compliance": 1.0, "global_reach": 0.5, "support": 0.5},
        "performance": {"performance": 3.0, "scalability": 2.5, "global_reach": 2.0, "cost": 1.0, "simplicity": 1.0, "compliance": 0.5, "lock_in_risk": 0.5, "support": 0.5},
        "compliance": {"compliance": 3.0, "support": 2.5, "global_reach": 2.0, "lock_in_risk": 1.5, "cost": 1.0, "performance": 1.0, "scalability": 1.0, "simplicity": 0.5},
        "simplicity": {"simplicity": 3.0, "support": 2.0, "cost": 1.5, "performance": 1.0, "scalability": 1.0, "lock_in_risk": 1.0, "compliance": 0.5, "global_reach": 0.5},
        "no-lock-in": {"lock_in_risk": 3.0, "cost": 2.0, "simplicity": 1.5, "performance": 1.0, "scalability": 1.0, "compliance": 1.0, "global_reach": 0.5, "support": 0.5}
    },
    
    "default_weights": {"cost": 1.5, "performance": 1.5, "scalability": 1.5, "simplicity": 1.0, "lock_in_risk": 1.5, "compliance": 1.0, "global_reach": 1.0, "support": 1.0},
    
    "judge_context": "competitive cloud provider evaluation",
    
    "tavily_query_templates": [
        "{company} cloud platform architecture overview {year}",
        "{company} cloud news announcements {year}",
        "{company} cloud reviews complaints problems {year}",
        "{company} cloud pricing changes {year}",
        "{company} vs AWS vs Azure comparison {year}"
    ],
    
    "hn_relevance_keywords": [
        "cloud", "aws", "azure", "gcp", "google cloud", "infrastructure", "iaas", "paas", "serverless",
        "kubernetes", "k8s", "docker", "container", "pricing", "egress", "cost", "billing",
        "region", "availability", "outage", "downtime", "migration", "multi-cloud", "hybrid", "terraform"
    ],
    
    "migration_query_templates": [
        "why we migrated from {company} to alternative cloud",
        "{company} cloud migration case study {year}",
        "left {company} cloud reasons engineering"
    ],
    
    "complaint_query_templates": [
        "{company} cloud pricing complaints {year}",
        "{company} cloud problems outages issues {year}",
        "{company} cloud egress costs expensive"
    ],
    
    "plaintiff_questions": [
        {"key": "company_name", "prompt": "Company name: ", "required": True},
        {"key": "team_size", "prompt": "Team size", "example": "10 engineers", "required": True},
        {"key": "budget", "prompt": "Monthly cloud budget", "example": "$10,000", "required": True},
        {"key": "use_case", "prompt": "Primary workload", "example": "SaaS platform, data pipeline, ML training", "required": True},
        {"key": "scale", "prompt": "Current + projected scale", "example": "100 VMs now, 500 in 18mo", "required": True},
        {"key": "current_cloud", "prompt": "Current cloud provider (if any)", "required": False},
        {"key": "compliance_reqs", "prompt": "Compliance requirements", "example": "HIPAA, SOC2, GDPR", "required": False},
        {"key": "regions", "prompt": "Required regions", "example": "US, EU, APAC", "required": False},
        {"key": "priority", "prompt": "Top priority (cost / performance / compliance / simplicity / no-lock-in)", "required": True}
    ],
    
    "eval_ground_truth": {
        "AWS": {"pricing_facts": ["free tier", "reserved instances", "savings plans", "spot"], "tech_facts": ["ec2", "s3", "lambda", "eks", "rds"], "known_complaints": ["egress costs", "complexity", "billing surprises"]},
        "Microsoft Azure": {"pricing_facts": ["free tier", "reserved", "spot", "hybrid benefit"], "tech_facts": ["vm", "blob storage", "aks", "functions"], "known_complaints": ["portal complexity", "naming conventions", "outages"]},
        "Google Cloud": {"pricing_facts": ["free tier", "committed use", "preemptible", "sustained use"], "tech_facts": ["gce", "gcs", "gke", "bigquery", "cloud run"], "known_complaints": ["support", "product shutdowns", "enterprise features"]}
    }
}