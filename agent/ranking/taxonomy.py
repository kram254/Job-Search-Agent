from typing import Dict, Optional, Set, Tuple, FrozenSet


TECH_TAXONOMY: Dict[str, Tuple[FrozenSet[str], str]] = {
    "python":        (frozenset({"py", "python3", "python2", "cpython"}), "language"),
    "javascript":    (frozenset({"js", "node.js", "nodejs", "es6", "ecmascript", "vanilla js"}), "language"),
    "typescript":    (frozenset({"ts", "tsx", "ts/js"}), "language"),
    "go":            (frozenset({"golang", "go lang"}), "language"),
    "rust":          (frozenset({"rust-lang", "rust programming"}), "language"),
    "java":          (frozenset({"jvm", "java 11", "java 17", "java 21", "core java"}), "language"),
    "c":             (frozenset({"c lang", "ansi c", "c programming"}), "language"),
    "cpp":           (frozenset({"c++", "c plus plus", "c/c++", "cpp"}), "language"),
    "csharp":        (frozenset({"c#", ".net", "dotnet", "asp.net", "asp net"}), "language"),
    "ruby":          (frozenset({"rb", "ruby lang"}), "language"),
    "php":           (frozenset({"php8", "php7", "php5"}), "language"),
    "swift":         (frozenset({"swift lang", "swift programming"}), "language"),
    "kotlin":        (frozenset({"kotlin android", "kotlin jvm"}), "language"),
    "scala":         (frozenset({"scala lang", "akka", "play framework"}), "language"),

    "react":         (frozenset({"reactjs", "react.js", "react hooks", "jsx", "react app"}), "frontend"),
    "vue":           (frozenset({"vuejs", "vue.js", "vue 3", "vue 2", "nuxt", "nuxtjs"}), "frontend"),
    "angular":       (frozenset({"angularjs", "angular 2+", "ng", "angular framework"}), "frontend"),
    "nextjs":        (frozenset({"next.js", "next js", "next framework"}), "frontend"),
    "svelte":        (frozenset({"sveltekit", "svelte kit"}), "frontend"),
    "html":          (frozenset({"html5", "html/css", "html markup"}), "frontend"),
    "css":           (frozenset({"scss", "sass", "less", "css3", "stylesheet"}), "frontend"),
    "tailwind":      (frozenset({"tailwind css", "tailwindcss", "tw"}), "frontend"),
    "graphql":       (frozenset({"gql", "graph ql", "apollo graphql", "apollo client"}), "frontend"),

    "react_native":  (frozenset({"react-native", "rn", "expo", "expo sdk"}), "mobile"),
    "flutter":       (frozenset({"dart flutter", "flutter/dart", "flutter sdk"}), "mobile"),
    "ios":           (frozenset({"swift ios", "xcode", "objective-c", "swiftui", "uikit"}), "mobile"),
    "android":       (frozenset({"android studio", "android sdk", "android development"}), "mobile"),

    "nodejs":        (frozenset({"node", "express.js", "expressjs", "express framework"}), "backend"),
    "django":        (frozenset({"django rest", "drf", "django framework", "django orm"}), "backend"),
    "fastapi":       (frozenset({"fast api", "fastapi framework"}), "backend"),
    "flask":         (frozenset({"flask python", "flask framework"}), "backend"),
    "spring":        (frozenset({"spring boot", "spring framework", "spring mvc", "spring cloud"}), "backend"),
    "rails":         (frozenset({"ruby on rails", "ror", "rails framework"}), "backend"),
    "nestjs":        (frozenset({"nest.js", "nestjs framework"}), "backend"),
    "laravel":       (frozenset({"laravel php", "php laravel"}), "backend"),

    "wordpress":     (frozenset({"wp", "elementor", "woocommerce", "wp-cli"}), "cms"),
    "drupal":        (frozenset({"drupal cms", "drupal 9", "drupal 10"}), "cms"),
    "contentful":    (frozenset({"sanity", "strapi", "headless cms", "contentful api"}), "cms"),

    "pandas":        (frozenset({"pd", "pandas dataframe", "pandas python"}), "data"),
    "numpy":         (frozenset({"np", "numpy arrays", "numpy python"}), "data"),
    "sql":           (frozenset({"structured query language", "t-sql", "pl/sql", "ansi sql"}), "data"),
    "postgresql":    (frozenset({"postgres", "pg", "psql", "pg database"}), "data"),
    "mysql":         (frozenset({"mariadb", "mysql db", "mysql server"}), "data"),
    "mongodb":       (frozenset({"mongo", "mongoose", "mongodb atlas", "mongo db"}), "data"),
    "redis":         (frozenset({"redis cache", "valkey", "redis cluster"}), "data"),
    "elasticsearch": (frozenset({"opensearch", "elastic", "kibana", "elk", "elastic stack"}), "data"),

    "pytorch":       (frozenset({"torch", "pytorch lightning", "pt"}), "ai"),
    "tensorflow":    (frozenset({"tf", "keras", "tf2", "tensorflow 2"}), "ai"),
    "scikit_learn":  (frozenset({"sklearn", "scikit-learn", "scikit learn"}), "ai"),
    "huggingface":   (frozenset({"hf", "transformers", "hugging face", "diffusers", "hf hub"}), "ai"),
    "langchain":     (frozenset({"langchain-core", "langchain community", "lcel", "langchain python", "lang chain"}), "ai"),
    "llm":           (frozenset({"large language model", "gpt", "claude", "gemini", "llama", "mistral", "openai api", "anthropic api", "llm api", "llms", "large language models", "language models"}), "ai"),
    "rag":           (frozenset({"retrieval augmented generation", "retrieval-augmented", "vector search", "rag pipeline", "agentic rag", "rag pipelines", "rag systems"}), "ai"),
    "vector_db":     (frozenset({"lancedb", "pinecone", "weaviate", "chroma", "qdrant", "pgvector", "milvus", "vector database", "vector databases", "vector store", "vector stores"}), "ai"),
    "mlops":         (frozenset({"llmops", "ml ops", "model serving", "mlflow", "wandb", "weights & biases", "model registry", "llm ops", "ai ops"}), "ai"),
    "computer_vision": (frozenset({"cv", "opencv", "object detection", "yolo", "image classification", "segmentation"}), "ai"),
    "nlp":           (frozenset({"natural language processing", "text classification", "named entity", "sentiment analysis"}), "ai"),
    "ai_agents":     (frozenset({"ai agent", "ai agents", "autonomous agent", "autonomous agents", "agentic ai", "agentic systems", "agentic automation", "multi-agent", "multi agent", "multiagent", "agent framework", "agent orchestration", "crewai", "autogen", "smolagents", "agent workflow"}), "ai"),
    "mcp":           (frozenset({"model context protocol", "mcp server", "mcp tools", "mcp protocol", "mcps"}), "ai"),
    "a2a":           (frozenset({"agent to agent", "agent-to-agent", "a2a protocol", "inter-agent"}), "ai"),

    "zapier":        (frozenset({"zapier automation", "zapier zaps"}), "automation"),
    "make":          (frozenset({"integromat", "make.com", "make automation"}), "automation"),
    "n8n":           (frozenset({"n8n automation", "n8n workflow"}), "automation"),
    "airflow":       (frozenset({"apache airflow", "dag", "airflow scheduler", "airflow operator"}), "automation"),
    "celery":        (frozenset({"celery worker", "celery beat", "celery task"}), "automation"),
    "prefect":       (frozenset({"prefect cloud", "prefect core", "prefect flow"}), "automation"),

    "docker":        (frozenset({"containerization", "dockerfile", "docker compose", "docker swarm"}), "infra"),
    "kubernetes":    (frozenset({"k8s", "kube", "helm", "kubectl", "kustomize"}), "infra"),
    "aws":           (frozenset({"amazon web services", "ec2", "s3", "lambda", "sagemaker", "eks", "ecs"}), "infra"),
    "gcp":           (frozenset({"google cloud", "google cloud platform", "bigquery", "gke", "vertex ai", "cloud run"}), "infra"),
    "azure":         (frozenset({"microsoft azure", "az", "aks", "azure devops", "azure functions"}), "infra"),
    "terraform":     (frozenset({"hcl", "infrastructure as code", "iac", "pulumi", "cdktf"}), "infra"),
    "ci_cd":         (frozenset({"github actions", "gitlab ci", "jenkins", "circleci", "ci/cd", "devops pipeline", "argocd"}), "infra"),
    "nginx":         (frozenset({"nginx proxy", "reverse proxy", "load balancer", "caddy", "traefik"}), "infra"),
    "linux":         (frozenset({"ubuntu", "debian", "centos", "rhel", "bash scripting", "shell scripting", "posix"}), "infra"),

    "kafka":         (frozenset({"apache kafka", "kafka streams", "event streaming", "kafka topic"}), "realtime"),
    "rabbitmq":      (frozenset({"amqp", "message queue", "message broker"}), "realtime"),
    "websockets":    (frozenset({"ws", "socket.io", "websocket protocol"}), "realtime"),
    "grpc":          (frozenset({"grpc protocol", "protobuf", "protocol buffers", "proto3"}), "realtime"),

    "figma":         (frozenset({"sketch", "adobe xd", "ui design", "ux design", "design system"}), "product"),
    "jira":          (frozenset({"jira software", "confluence", "atlassian", "agile board"}), "product"),
    "notion":        (frozenset({"notion.so", "notion workspace", "notion database"}), "product"),

    "electron":      (frozenset({"electronjs", "electron app", "electron framework"}), "desktop"),
    "tauri":         (frozenset({"tauri app", "tauri framework", "tauri 2"}), "desktop"),

    "pytest":        (frozenset({"unit tests", "integration tests", "tdd", "bdd", "test suite", "test coverage"}), "testing"),
    "jest":          (frozenset({"jest testing", "testing library", "vitest", "mocha"}), "testing"),
    "cypress":       (frozenset({"e2e testing", "cypress io", "playwright testing", "end-to-end"}), "testing"),
    "selenium":      (frozenset({"selenium webdriver", "selenide", "selenium grid"}), "testing"),

    "sap":           (frozenset({"sap erp", "sap hana", "sap s/4hana", "sap basis"}), "enterprise"),
    "salesforce":    (frozenset({"sfdc", "salesforce crm", "force.com", "apex", "soql"}), "enterprise"),
}

TECH_CATEGORY: Dict[str, Set[str]] = {}
for _skill, (_aliases, _cat) in TECH_TAXONOMY.items():
    TECH_CATEGORY.setdefault(_cat, set()).add(_skill)

BLOCKED_ADJACENCY_CATEGORIES: FrozenSet[str] = frozenset({
    "language", "frontend", "mobile", "desktop", "cms", "enterprise"
})

SENIORITY_HARD_CAPS = {
    "wrong_field":        15,
    "fresher_3yr":        30,
    "junior_5yr":         38,
    "junior_3yr":         45,
    "mid_7yr":            48,
    "no_direct_match":    42,
    "adjacent_only":      52,
}

WRONG_FIELD_TERMS: FrozenSet[str] = frozenset({
    "plumber", "electrician", "nurse", "physician", "doctor", "surgeon",
    "dentist", "veterinarian", "pharmacist", "lawyer", "attorney", "paralegal",
    "accountant", "auditor", "actuary", "carpenter", "mason", "welder",
    "painter", "roofer", "landscaper", "gardener", "chef", "baker",
    "bartender", "server", "waiter", "waitress", "cook", "cashier", "barista",
    "truck driver", "bus driver", "taxi driver", "pilot", "flight attendant",
    "mechanic", "hvac", "boilermaker", "pipefitter", "ironworker",
    "steelworker", "sheet metal", "real estate agent", "insurance agent",
    "loan officer", "mortgage broker", "security guard", "police officer",
    "firefighter", "paramedic", "lifeguard", "social worker", "teacher",
    "professor",
})

RED_FLAGS: FrozenSet[str] = frozenset({
    "guaranteed income",
    "be your own boss",
    "unlimited earning potential",
    "no experience needed",
    "make money fast",
    "passive income",
    "pyramid scheme",
    "work from home opportunity",
})

ROLE_KEYWORDS: Dict[str, list] = {
    "engineer":   ["engineer", "developer", "programmer", "architect", "dev"],
    "manager":    ["manager", "director", "head", "vp", "chief", "lead"],
    "scientist":  ["scientist", "researcher", "analyst"],
    "consultant": ["consultant", "advisor", "specialist"],
}

DELIVERABLE_KEYWORDS: Dict[str, list] = {
    "build":   ["build", "develop", "create", "implement", "ship"],
    "scale":   ["scale", "optimize", "improve", "enhance"],
    "design":  ["design", "architect", "plan", "roadmap"],
    "operate": ["operate", "maintain", "monitor", "support", "deploy"],
}


def resolve_canonical(term: str) -> Optional[str]:
    term_lower = term.strip().lower()
    if term_lower in TECH_TAXONOMY:
        return term_lower
    for canonical, (aliases, _cat) in TECH_TAXONOMY.items():
        if term_lower in aliases:
            return canonical
        if term_lower == canonical:
            return canonical
    return None


def get_category(canonical: str) -> Optional[str]:
    entry = TECH_TAXONOMY.get(canonical)
    if entry:
        return entry[1]
    return None


def skills_are_adjacent(skill_a: str, skill_b: str) -> bool:
    cat_a = get_category(skill_a)
    cat_b = get_category(skill_b)
    if cat_a is None or cat_b is None:
        return False
    if cat_a != cat_b:
        return False
    if cat_a in BLOCKED_ADJACENCY_CATEGORIES:
        return False
    return True
