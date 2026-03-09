"""
Database Vertical Configuration (v2)
====================================
Config for database vendor comparisons.
NOTE: Vendors moved to vendors.json - this file only has dimensions, keywords, questions.
"""

DATABASE_CONFIG = {
    "name":         "database",
    "display_name": "Database Vendors",
    "description":  "Vector databases, document stores, and data platforms",
    
    "dimensions": [
        "cost", "performance", "scalability", "simplicity",
        "lock_in_risk", "vector_capability", "ecosystem"
    ],
    
    "dimension_keywords": {
        "cost": ["price", "pricing", "cost", "expensive", "cheap", "free", "billing", "dollar", "$", "budget", "tier", "plan", "subscription", "pay", "monthly", "annual", "usage-based"],
        "performance": ["latency", "speed", "fast", "slow", "performance", "benchmark", "throughput", "millisecond", "ms", "query time", "response time", "qps", "p99", "p95"],
        "scalability": ["scale", "scaling", "million", "billion", "vector", "sharding", "cluster", "node", "distributed", "horizontal", "vertical", "capacity", "petabyte", "terabyte", "auto-scale"],
        "simplicity": ["easy", "simple", "complex", "difficult", "setup", "manage", "operational", "maintenance", "devops", "configure", "learning curve", "documentation", "onboarding", "developer experience"],
        "lock_in_risk": ["lock-in", "vendor", "migration", "portable", "open source", "proprietary", "switch", "alternative", "replace", "moved away", "sspl", "license"],
        "vector_capability": ["vector", "embedding", "semantic", "similarity", "ann", "hnsw", "ivf", "cosine", "euclidean", "dimension", "dense", "sparse", "hybrid search", "rag", "retrieval"],
        "ecosystem": ["integration", "sdk", "driver", "client", "api", "plugin", "connector", "langchain", "llamaindex", "community", "support", "documentation", "enterprise", "managed", "cloud"]
    },
    
    "priority_weights": {
        "cost": {"cost": 3.0, "lock_in_risk": 2.0, "simplicity": 1.5, "performance": 1.0, "scalability": 1.0, "vector_capability": 1.0, "ecosystem": 0.5},
        "performance": {"performance": 3.0, "scalability": 2.5, "vector_capability": 2.0, "cost": 1.0, "simplicity": 0.5, "lock_in_risk": 0.5, "ecosystem": 0.5},
        "simplicity": {"simplicity": 3.0, "ecosystem": 2.0, "cost": 1.5, "performance": 1.0, "vector_capability": 1.0, "scalability": 0.5, "lock_in_risk": 0.5},
        "no-lock-in": {"lock_in_risk": 3.0, "cost": 2.0, "ecosystem": 1.5, "simplicity": 1.0, "performance": 1.0, "scalability": 1.0, "vector_capability": 1.0},
        "enterprise": {"scalability": 3.0, "ecosystem": 2.5, "performance": 2.0, "lock_in_risk": 1.5, "cost": 1.0, "simplicity": 0.5, "vector_capability": 1.5}
    },
    
    "default_weights": {"cost": 1.5, "performance": 1.5, "scalability": 1.5, "simplicity": 1.0, "lock_in_risk": 1.5, "vector_capability": 1.5, "ecosystem": 1.0},
    
    "judge_context": "competitive vector database evaluation focusing on RAG and semantic search use cases",
    
    "tavily_query_templates": [
        "{company} database architecture technical overview {year}",
        "{company} database news announcements {year}",
        "{company} database reviews complaints problems {year}",
        "{company} database developer sentiment reddit migration {year}"
    ],
    
    "hn_relevance_keywords": [
        "database", "db", "vector", "search", "nosql", "sql", "performance", "scale", "cloud", "storage", "query",
        "mongodb", "pinecone", "weaviate", "cassandra", "architecture", "latency", "benchmark", "pricing",
        "migration", "alternative", "vs", "versus", "embedding", "rag", "semantic"
    ],
    
    "migration_query_templates": [
        "why we migrated from {company} engineering blog",
        "{company} migration case study {year}",
        "left {company} reasons engineering team"
    ],
    
    "complaint_query_templates": [
        "{company} pricing expensive complaints {year}",
        "{company} problems real users production issues",
        "{company} cost at scale problems"
    ],
    
    "plaintiff_questions": [
        {"key": "company_name", "prompt": "Company name: ", "required": True},
        {"key": "team_size", "prompt": "Team size", "example": "3 engineers", "required": True},
        {"key": "budget", "prompt": "Monthly budget", "example": "$2000", "required": True},
        {"key": "use_case", "prompt": "Primary use case", "example": "RAG pipeline, semantic search", "required": True},
        {"key": "scale", "prompt": "Current + 18mo projection", "example": "10M to 500M vectors", "required": True},
        {"key": "cloud", "prompt": "Cloud provider", "example": "AWS, GCP, Azure", "required": False},
        {"key": "priority", "prompt": "Top priority (cost / performance / simplicity / no-lock-in)", "required": True}
    ],
    
    "eval_ground_truth": {
        "MongoDB": {"pricing_facts": ["atlas free tier", "serverless", "dedicated"], "tech_facts": ["atlas vector search", "document model", "aggregation"], "known_complaints": ["atlas pricing at scale", "sspl license"]},
        "Pinecone": {"pricing_facts": ["starter free", "standard", "enterprise", "serverless"], "tech_facts": ["managed vector db", "metadata filtering", "namespaces"], "known_complaints": ["cost at scale", "vendor lock-in"]},
        "Weaviate": {"pricing_facts": ["open source", "cloud free tier", "enterprise"], "tech_facts": ["vectorizer modules", "graphql api", "multi-tenancy"], "known_complaints": ["memory consumption", "operational complexity"]}
    }
}