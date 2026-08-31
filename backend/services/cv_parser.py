import re

TECH_KEYWORDS = {
    # == Programming Languages ==
    "python", "java", "c", "c++", "cpp", "c#", "csharp", "javascript", "js", "typescript", "ts",
    "sql", "pl/sql", "php", "go", "golang", "kotlin", "matlab", "swift", "objective c", "rust", "ruby", "dart", "scala", "r",
    "visual basic", "vba", "oscript", "solidity",
    
    # == Scripting & Shell ==
    "ecmascript", "groovy", "perl", "lua", "bash", "powershell", "emacs lisp", "gml",

    # == Frontend, UI & Visualization ==
    "html", "html5", "css", "css3", "react", "react.js", "reactjs", "react native", "angular", "angular material", "vue", "vue.js", "vuejs",
    "next.js", "nextjs", "nuxt", "nuxtjs", "tailwind", "tailwind css", "tailwindcss", "material ui", "mui", "bootstrap",
    "ant design", "primeng", "quasar", "vuetify", "shadcn", "chakra ui", "styled-components",
    "redux", "redux toolkit", "mobx", "zustand", "pinia", "vuex", "ngrx", "ngxs",
    "rtk query", "react-query", "tanstack query", "rxjs", "axios", "graphql", "apollo", "fetch api",
    "sass", "scss", "less", "vite", "webpack", "npm", "yarn", "pnpm", "figma", "d3.js", "chart.js", "chartjs", "three.js",
    "power bi", "power bi report server", "power query", "dax", "datalense", "datalens", "plotly", "dash", "tableau", "tableau public", "luxms bi",
    "visiology", "matplotlib", "seaborn", "plantuml", "balsamiq", "ms visio", "aris", "business studio",
    "erwin", "erwin process modeler", "erwin data modeler", "electron", "winforms", "oracle apex",
    "yii", "yii 1.x", "yii2", "bitrix", "jquery", "symfony encore", "next intl", "i18next", "react hook form", "zod", "бэм", "bem",
    "yup", "formik", "react router", "finebi", "vanilla js", "blade", "streamlit", "composition api", "veevalidate", "module federation", "socket.io", "swiper", "material react table", "jsp", "jstl", "backbone", "bpmn.io",
    "tanstack router", "tanstack table", "react-toastify", "i18n", "css modules", "husky", "eslint", "prettier",

    # == Backend Frameworks & Architecture ==
    "node.js", "nodejs", "express", "express.js", "nest", "nestjs", "django", "drf", "django admin", "django channels", "flask", "fastapi", "asgi",
    "starlette", "aiohttp", "httpx", "asyncio", "celery", "sqlalchemy", "alembic", "pydantic",
    "spring", "spring boot", "spring core", "spring data", "spring mvc", "spring security", "spring test", "spring cloud", "spring webflux", "spring integration", "spring web services",
    ".net", ".net framework", ".net core", "asp.net", "asp.net core", "asp.net mvc", "asp.net webapi", "mediatr", "masstransit", "serilog", "linq", "wcf",
    "laravel", "symfony", "entity framework", "entity framework core", "hibernate", "jpa", "jdbc",
    "axum", "tokio", "actix-web", "gorm", "sqlx", "camunda", "camunda bpm", "fasthttp", "gin", "temporal",
    "grpc", "websocket", "websockets", "openapi", "jwt", "protobuf", "tls", "mtls", "oauth", "oauth 2.0", "rbac",
    "микросервисы", "микросервисная архитектура", "bff", "webrtc", "cqrs", "gof", "circuit breaker", "saga", "clean architecture", "solid",
    "ajax", "openid", "websso", "jcp", "jmx", "uber cadence", "maven", "flyway", "querydsl", "jackson", "mapstruct", "kafka streams",
    "feign client", "keycloak", "graceful shutdown", "middleware", "msa", "eda", "http/https",
    "refit", "quartz", "dapper", "graphql api", "telegram api", "signalr", "automapper", "wolverine", "mapster", "prisma", "typeorm", "pgvector", "api gateway", "avro", "request-reply", "pub/sub",
    "laravel queue", "guzzle async", "aop", "openfeign", "resilience4j", "spel", "actuator", "cel", "hazelcast", "jax-ws", "jms", "идемпотентность", "ретраи", "оркестрация", "хореография", "soa", "asyncapi", "mqtt", "fix", "fast", "gunicorn", "j2se", "j2ee", "servlets", "jvm",
    "java ee", "spring web", "apache tomcat", "echo", "protocol buffers", "goroutine", "goroutines", "viper", "zap", "golangci-lint", "expressjs", "prisma orm", "sequelize", "supertest", "turborepo", "asp.net web api", "autofac", "python-разработчик", "python backend", "django rest framework", "django orm", "ruff", "mypy",

    # == Systems Programming & Low-Level ==
    "lkm", "linux kernel modules", "posix", "posix api", "vfs", "ipc", "mmap", "pthreads", "signals", "gcc", "clang", "makefile", "cmake", "gdb", "valgrind", "perf", "strace", "cargo", "egui", "macroquad",
    "embedded linux", "cuda", "nvidia", "gpu",

    # == Databases, Data Engineering & GIS ==
    "postgresql", "postgres", "mysql", "mongodb", "mongo", "redis", "elasticsearch", "clickhouse",
    "mssql", "sql server", "ms sql server", "ms sql 2019", "oracle", "db2", "nosql", "cassandra", "mariadb", "sqlite", "exadata", "hsqldb",
    "pgbouncer", "ytsaurus", "yql", "greenplum", "foundationdb", "etcd", "dragonfly", "neo4j", "arangodb", "supabase", "qdrant", "dbeaver",
    "minio", "dynamodb", "azure cosmos db", "google datastore", "data marts", "sap erp", "hbase",
    "spark", "apache spark", "pyspark", "airflow", "apache airflow", "kafka", "hadoop", "hdfs", "hive", "nifi", "apache nifi", "zookeeper",
    "dbt", "luigi", "redshift", "bigquery", "snowflake", "apache iceberg", "iceberg", "openmetadata", "apache superset", "superset", "apache solr",
    "qliksense", "qlik sense", "nprinting", "qmc", "sense api", "qv api", "qlik talend", "qlik replicate", "debezium",
    "pytorch", "tensorflow", "scikit-learn", "sklearn", "mlflow", "catboost", "xgboost", "pandas", "numpy",
    "scrapy", "beautiful soup", "bs4", "delta lake", "keras", "networkx", "openrefine", "weka",
    "trino", "databricks", "jupyterhub", "dvc", "seldon core", "kinesis", "modus etl", "informatica powercenter", "apache atlas", "great expectations", "data proc", "arenadata", "fineops", "polars", "scipy", "rl", "reinforcement learning",
    "geoserver", "gdal", "postgis", "s2t", "бфт", "parquet", "orc", "metabase", "dataops", "data observability", "sla/slo management", "data contracts", "data management",
    "elastic", "apache kafka", "jupyter", "google colab", "машинное обучение", "data science", "deep learning", "глубокое обучение", "нейронные сети", "обучение с учителем", "обучение с подкреплением", "lightgbm", "детекция аномалий", "временные ряды", "кластеризация", "графовый анализ", "графовые бд", "shap", "feature engineering", "feature store", "feast", "скоринг", "кредитный скоринг", "фрод-мониторинг", "рекомендательные системы", "recsys", "precision", "recall", "метрики качества модели", "датасет", "разметка данных", "train/test/валидационная выборка",

    # == Mobile Development (iOS, Android, Cross-platform) ==
    "ios", "android sdk", "jetpack compose", "viewbinding", "coroutines", "stateflow", "retrofit", "okhttp", "webview", "deep links", "ble", "nfc", "biometrics", "kmp", "kotlin multiplatform", "android studio profiler", "hilt", "koin", "room", "jetpack datastore", "hive", "drift", "sharedpreferences", "mvi", "rxjava", "dio", "ktor", "kotlinx.coroutines", "kotlinx.serialization", "sharedflow", "flowmvi", "android architecture components",
    "swiftui", "uikit", "snapkit", "mapkit", "xcode", "interface builder", "gcd", "structured concurrency", "operationqueue", "uicollectionview", "uitableview", "apns", "arc", "urlsession", "codable", "jsonserialization", "apple sdk", "google sdk", "core data", "userdefaults", "keychain", "xamarin", "xamarin.native", "avfoundation", "core image", "corevideo", "core animation", "mvvm-c", "mvvmcross", "swinject", "alamofire", "centrifuge", "livekit", "realm", "fcm", "cloud messaging", "remote config",
    "flutter", "compose multiplatform", "bloc", "provider", "riverpod", "getit", "gorouter", "freezed", "apache cordova", "activity", "fragment", "sqldelight", "motionlayout", "type-safe navigation", "custom view", "speechrecognizer", "gson", "glide", "lottie", "canvas", "yandex appmetrica", "firebase analytics", "crashlytics", "gradle version catalog", "agp", "appsweep", "leakcanary", "timber", "firebase app distribution", "modo", "cicerone", "mvikotlin", "mvicore", "gradle modules", "toothpick", "react native bridge", "android studio",
    "autolayout", "mvc", "mvp", "mvvm", "coordinator", "json/codable", "moya", "async/await", "coredata", "cocoapods", "spm", "android", "flow", "livedata", "navigation component", "compose testing", "firebase auth", "firebase realtime database", "coil", "autoroute", "deeplinks", "shared preferences", "firebase", "yandexmaps", "yandexads", "matrix sdk", "fluttermap", "json_serializable", "easy_localization", "equatable",

    # == DevOps, Cloud & IaC ==
    "aws", "aws lambda", "aws s3", "aws athena", "aws glue", "aws sqs", "aws sns", "aws ec2", "aws rds", "aws eks", "aws cloudfront", "aws aurora", "aws secrets manager", "aws iam", "aws ecr", "aws kms", "aws ecs", "aws emr", "lake formation",
    "gcp", "azure", "azure devops", "azure api gateway", "azure functions", "azure app service", "azure key vault", "azure blob storage", "azure backup", "azure data factory", "azure aks", "azure container registry", "azure event hubs", "adls gen2", "azure monitor", "synapse analytics", "azure sql managed instance",
    "digital ocean", "digitalocean", "yandex cloud", "yandex s3", "ydb", "hetzner cloud", "hetzner",
    "docker", "docker compose", "docker-compose", "podman", "kubernetes", "k8s", "helm", "kustomize", "istio", "openshift", "rancher", "talos",
    "terraform", "terragrunt", "cloudformation", "bicep", "pulumi", "ansible", "chef", "puppet", "salt",
    "gitlab ci", "gitlab ci/cd", "github actions", "jenkins", "jenkins x", "bitbucket pipelines", "teamcity", "argocd", "jfrog artifactory", "gitflic", "bamboo", "gitops", "ant",
    "nginx", "nginx ingress", "apache", "apache 2.4", "tomcat", "iis", "traefik", "vyos", "haproxy", "envoy", "alb", "tlb",
    "rabbitmq", "activemq", "ibm mq", "google pub/sub", "sonarqube", "snyk", "trivy",
    "hashicorp vault", "kaniko", "cert-manager", "fail2ban", "nftables", "gradle", "liquibase", "testcontainers",
    "git", "gitlab", "github", "bitbucket", "svn", "tfs", "mercurial",
    "криптопро", "криптопро csp", "диадок", "сбис", "saby", "active directory", "lan", "ceph", "nexus", "nfs",
    "abac", "s3", "shell", "iac", "infrastructure as code", "gitlab runner", "argo cd", "fluxcd", "elastic stack", "openstack", "proxmox", "consul", "nomad", "linkerd", "service mesh", "packer", "ci/cd", "object storage", "lakefs", "vault", "harbor", "datahub", "on-prem", "закрытый контур",

    # == Security & AppSec ==
    "owasp", "owasp top 10", "cwe", "sans top 25", "secure sdlc", "threat modeling", "sast", "dast", "burp suite", "owasp zap", "semgrep", "checkmarx", "nuclei", "waf", "api security", "defectdojo", "appsec", "ssl pinning", "secure storage", "анализ уязвимостей", "adversarial robustness toolbox", "art", "pci dss", "talsec appicrypt", "pki", "sso", "iso 27001", "seccomp", "ptrace", "auditd", "inotify",

    # == Monitoring & Logging ==
    "grafana", "prometheus", "zabbix", "datadog", "influxdb", "new relic", "splunk",
    "elk", "elk stack", "efk", "efk stack", "logstash", "kibana", "fluentd", "loki", "promtail", "graylog",
    "opentelemetry", "otlp", "victoriametrics", "micrometer", "pgwatch", "jaeger", "pprof", "log4j", "cloudwatch", "alertmanager", "prompp", "vector",
    "observability", "мониторинг моделей",

    # == System Analysis & Methodologies ==
    "bpmn", "bpmn 2.0", "uml", "erd", "er", "er-diagrams", "dfd", "swagger", "rest", "rest api", "soap",
    "json", "xml", "xsd", "jira", "confluence", "miro", "draw.io", "lucidchart", "docusaurus",
    "agile", "scrum", "kanban", "safe", "waterfall", "lean", "xp", "экстремальное программирование",
    "idef", "idef0", "epc", "eepc", "c4 model", "c4", "as-is", "to-be", "as-is/to-be", "archimate",
    "тз", "чтз", "пми", "гост", "гост 34.602", "гост 19", "user story", "use case", "release notes", "troubleshooting guide", "brd", "fsd", "job story", "user story mapping", "концепция", "технический проект", "пояснительная записка", "руководство администратора", "руководство пользователя", "паспорт системы", "шаблоны документов", "ms office",
    "data vault", "data vault 2.0", "data vault modeling", "star schema", "snowflake schema", "kimball", "scd type 2", "snapshot tables",
    "схема звезда", "схема снежинка", "медальонная архитектура", "денормализация", "нормализация",
    "structurizr", "archi", "sequence diagram", "state diagram", "itam", "cmdb", "snmp", "wmi", "ssh", "itsm", "service desk", "cjm", "rtm", "data lakehouse", "data mesh", "oms", "scm", "plm", "backlog refinement", "rice", "moscow", "story points", "babok", "b2b",
    "eda", "cvm", "acrm", "nba/nbo", "a/b-тестирование", "uplift-моделирование", "roi", "ltv", "churn", "customer development", "снэв",
    "ddd", "acid", "rate-limiting", "sla", "health checks", "data lineage", "data governance", "data quality", "rca", "nlp", "genai", "cuped", "bayesian statistics", "adr", "psm1", "бюджетирование", "эдо", "юзэдо", "кэп", "drp", "disaster recovery plan", "rto/rpo", "пруденциальная отчетность", "банковский бухгалтерский учет", "указание бр 6406-у", "управление рисками", "управление стейкхолдерами", "мчд", "пэп", "укэп", "реверс-инжиниринг", "mapping",
    "проектный менеджер", "управление проектами", "управление портфелем проектов", "жизненный цикл проекта", "инициация проекта", "ресурсное планирование", "управление ресурсами", "планирование бюджета", "управление бюджетом", "контроль бюджета", "контроль сроков", "контроль скоупа", "контроль качества", "оценка трудозатрат", "risk management", "кросс-функциональная команда", "delivery", "приоритизация бэклога", "проектная документация", "проектные метрики", "статусная отчетность", "критерии приемки", "пилотный запуск", "эскалация", "dor", "dod", "linear", "huly",

    # == CRM, ERP & Enterprise Platforms (incl. 1C & SAP Hybris) ==
    "1c", "1с", "1с:предприятие", "1с:erp", "1с:ут", "1с:бп", "1с:управление торговлей", "1с:зарплата и управление персоналом", "1с:зуп", "1с:бухгалтерия", "1с:управление холдингом", "1с:медицина", "1с:розница", "1с:налоговый мониторинг", "axelot", "бсп", "скд", "enterprisedata", "конвертация данных", "edt", "ado", "язык запросов 1с", "клиент-серверное взаимодействие",
    "bitrix24", "retailcrm", "salesforce", "salesforce crm", "salesforce marketing cloud", "mindbox", "cdp", "kaiten", "intland", "youtrack", "sap", "sugarcrm", "suitecrm", "нота юнион", "elma365", "opentext content server", "contentai", "edms", "trello", "notion", "enterprise architect", "ocr", "zendesk", "ms project", "microsoft project", "roadmap planner", "asana", "clickup", "redmine", "slack", "google workspace", "внедрение erp", "tms", "гис эпд", "скб контур", "radius", "modullar", "sap hybris", "sap hybris commerce", "sap hybris cx commerce", "impex", "flexible search", "cronjobs", "wcms",
    "1с edt", "встроенный язык 1с", "типовые конфигурации", "управляемые формы", "внешние обработки", "печатные формы", "commerceml", "1с:документооборот", "1с:ух", "1с:ка", "1с:унф", "1с 7.7", "1с 8.x", "1с:профессионал", "http-сервисы 1с", "rls", "1с-битрикс", "битрикс24", "bitrix framework", "d7", "bitrixvm", "bitrix-env", "bitrix composite", "highload-blocks", "инфоблоки", "агенты битрикс", "события битрикс", "компоненты битрикс", "кастомные компоненты", "коробочная версия битрикс24", "bitrix24 enterprise", "bitrix24 cloud", "bitrix24 on-premise", "монитор производительности битрикс",

    # == Blockchain & Web3 ==
    "hardhat", "metamask",

    # == AI, LLM, Computer Vision & Voice Tools ==
    "cloud code", "chatgpt", "claude", "cursor", "rag", "ai agents", "langchain", "rasa", "nlu", "vui", "asr", "tts", "yandex speechkit", "salutespeech", "voiceflow", "label studio", "chromadb", "векторные бд", "эмбеддинги", "семантический поиск", "промпт-инжиниринг", "анонимизация данных", "langgraph", "llamaindex", "sentence-transformers", "openai api", "function calling", "computer vision", "transformers", "clip", "distilbert", "resnet", "helsinki-nlp",
    "автоэнкодеры", "llm", "transformer", "hugging face", "spacy", "nltk", "gensim", "ner", "named entity recognition", "text classification", "agentic rag", "чанкинг", "chunking", "n8n", "mcp", "ai-агенты", "мультиагентные системы", "субагенты", "tool calling", "structured output", "few-shot", "prompt engineering", "файн-тюнинг", "fine-tuning", "post-training", "lora", "peft", "галлюцинации", "guardrails", "llm-as-a-judge", "evals", "data curation", "мультимодальные модели", "vllm", "ollama", "llama.cpp", "инференс", "квантизация", "open-source модели", "gigachat", "yandexgpt", "t-lite", "saiga", "vikhr", "qwen", "llama", "deepseek", "mistral", "векторная бд", "vector store", "milvus", "weaviate", "faiss", "pinecone", "chroma", "cosine similarity", "l2-расстояние", "opencv", "cv2", "yolo", "detectron2", "albumentations", "детекция объектов", "объектная детекция", "сегментация", "классификация изображений", "детекция дефектов", "видеоаналитика", "slam", "point cloud", "облако точек", "lidar", "3d-сегментация", "open3d", "pcl", "pdal", "cloudcompare", "scan-to-bim", "e57", "las", "laz", "ply", "obj", "onnx", "tensorrt", "triton inference server", "cpu-инференс", "fp16", "fp8", "mixed precision", "распределённое обучение", "ddp", "fsdp", "moe", "mlops", "kubeflow", "argo workflows", "weights & biases", "clearml", "evidently", "версионирование моделей", "human-in-the-loop", "aws sagemaker", "gcp vertex ai", "azure ml", "cloudera ai",

    # == Testing ==
    "jest", "cypress", "playwright", "vitest", "mocha", "jasmine", "karma", "react testing library", "angular testing library", "vue test utils",
    "selenium", "selenium webdriver", "appium", "postman", "jmeter", "pytest", "junit", "junit 5", "mockito",
    "xunit", "nunit", "moq", "fluentassertions", "fluentvalidation", "autofixture",
    "phpunit", "codeception", "testify", "gomock", "soapui", "devtools", "uat",
    "testrail", "zephyr", "restsharp", "charles proxy", "charles", "fiddler", "adb", "xcode", "xctest", "espresso", "compose ui test", "kotest",
    "functional testing", "regression testing", "e2e testing", "api testing", "desktop testing", "ui testing", "mobile testing", "shift-left testing", "gui testing", "usability testing", "smoke testing", "sanity testing", "test cases", "acceptance criteria", "чек-листы",
    "selenide", "restassured", "allure", "testflight", "perfectpixel", "cucumber", "mstest", "wiremock", "loadrunner", "allure report", "gatling", "performance center", "mockk", "vanessa automation", "yaxunit", "debug", "memory leaks", "root cause анализ", "pytest-bdd", "pom", "page object model", "schemathesis", "pylint", "black", "flake8", "locust", "testng", "insomnia", "k6", "visual studio", "karate framework", "karate",
    "tdd", "ginkgo", "gomega", "unittest", "qa-инженер", "инженер по тестированию", "инженер-тестировщик", "manual qa", "ручное тестирование", "функциональное тестирование", "регрессионное тестирование", "интеграционное тестирование", "исследовательское тестирование", "нагрузочное тестирование", "etl testing", "dwh testing", "тест-кейс", "чек-лист", "тест-план", "тестовый сценарий", "баг-репорт", "defect management", "тест-дизайн", "testit", "testlink", "aqa engineer", "автоматизация тестирования", "автоматизированное тестирование", "автотесты", "requests", "rest assured", "reportportal"
}

SENIORITY_KEYWORDS = {
    "junior": "Junior", "джуниор": "Junior", "младший": "Junior", "trainee": "Junior", "стажер": "Junior", "стажёр": "Junior",
    "middle": "Middle", "мидл": "Middle", "mid": "Middle", "midle": "Middle",
    "senior": "Senior", "сеньор": "Senior", "сеньёр": "Senior", "старший": "Senior", "senoir": "Senior",
    "lead": "Lead", "лид": "Lead", "ведущий": "Lead", "principal": "Lead", "staff": "Lead", "architect": "Lead", "архитектор": "Lead"
}

DIRECTION_KEYWORDS = {
    "Data Engineer": [
        "data engineer", "дата инженер", "инженер данных"
    ],
    "Data Analyst / BI": [
        "data analyst", "аналитик данных", "bi аналитик", "bi-аналитик"
    ],
    "System / Business Analyst": [
        "system analyst", "системный аналитик", "business analyst", "бизнес аналитик", "бизнес-аналитик"
    ],
    "Solution / Enterprise Architect": [
        "solution architect", "enterprise architect", "it-архитектор", "проектирование архитектуры",
    ],
    "Project / Product Manager": [
        "project manager", "product manager", "руководитель проекта", "руководитель продукта",
        "scrum master", "agile coach", "проектный менеджер"
    ],
    "DevOps / SRE / SysAdmin": [
        "devops", "девопс", "системный администратор", "сисадмин", "sre"
    ],
    "QA / Testing": [
        "qa", "aqa", "тестировщик", "automation engineer", "qa engineer", "тестирование", 
        "qa-инженер", "инженер по тестированию", "инженер-тестировщик", "manual qa", "aqa engineer"
    ],
    "Backend Developer": [
        "backend", "бэкенд", "python backend", "python-разработчик"
    ],
    "Frontend Developer": [
        "frontend", "фронтенд", "javascript developer", "typescript developer", "веб-разработчик"
    ],
    "1C Specialist": [
        "1c", "1с", "1с разработчик", "1с-программист"
    ],
    "SAP Specialist": [
        "sap", "sap hybris", "impex", "flexible search", "wcms", "sap erp", "sap commerce"
    ]
}

DOMAIN_KEYWORDS = {
    "E-commerce & Retail": [
        "e-commerce", "ecommerce", "e commerce", "электронная коммерция", "продажи/электронная коммерция",
        "маркетплейс", "маркетплейсы", "b2b-маркетплейсы", "b2b коммерция", "коммерция", "ритейл", "retail", "оптовая торговля"
    ],
    "EdTech & Education": [
        "образование", "обучение", "edtech", "ed-tech", "ed tech", "эдтех", "эдтеч"
    ],
    "FinTech, Banking & Insurance": [
        "банк", "банки", "банкинг", "banking", "финансы", "финтех", "fintech", "fin tech",
        "финансовый сектор", "инвестиции", "инвестиционный банкинг", "страхование", "insurance"
    ],
    "MedTech & Healthcare": [
        "медицина", "медтех", "medtech", "med-tech", "здоровье", "здравоохранение", "healthcare"
    ],
    "HR Tech": [
        "кадры", "управление персоналом", "hr", "hr tech", "hr-tech", "hrtech"
    ],
    "Logistics & Transport": [
        "логистика", "транспорт", "логистика и грузоперевозки", "логистика и транспорт", "logistics"
    ],
    "GovTech & Public Sector": [
        "государственные ис", "государственные услуги", "государственный сектор", "govtech", "b2g", "закупки"
    ],
    "Media, Entertainment & Social": [
        "медиа", "новостные и медийные платформы", "социальные сети", "развлечения", "игровая индустрия", "gamedev", "гемблинг"
    ],
    "Manufacturing & Industry": [
        "производство", "производство (fmcg)", "промышленность", "реальный сектор", "автомобильная промышленность", 
        "агропромышленность", "горнодобывающая промышленность", "mes-системы", "тоир"
    ],
    "Energy & Oil/Gas": [
        "энергетика", "нефть и газ", "oil and gas"
    ],
    "Cloud & Infrastructure": [
        "инфраструктура", "веб-инфраструктура", "инфраструктурные сервисы", "облачная инфраструктура", 
        "облачные платформы", "облачные сервисы", "облачные технологии", "cloud"
    ],
    "Cybersecurity": [
        "безопасность", "информационная безопасность", "безопасность данных", "cybersecurity", "infosec"
    ],
    "AI & Data": [
        "ии и анализ данных", "аналитика данных", "искусственный интеллект", "ai", "artificial intelligence", "ai/ml-интеграции"
    ],
    "Telecom": [
        "телеком", "телекоммуникации", "telecom"
    ],
    "Enterprise & Integration": [
        "информационные технологии", "ит", "it-интеграция", "системная интеграция", "системные интеграции",
        "информационные технологии/системная интеграция", "внутренние системы", "корпоративные платформы",
        "корпоративные порталы", "корпоративные системы", "корпоративный сектор", "системное по", "софт",
        "enterprise", "enterprise saas / paas", "erp", "crm", "электронный документооборот", "saas", "автоматизация"
    ],
    "Real Estate & PropTech": [
        "недвижимость", "proptech", "prop tech"
    ],
    "IoT": [
        "iot", "iot-мониторинг", "internet of things"
    ],
    "Marketing & Services": [
        "маркетинг", "услуги", "услуги для бизнеса", "туризм", "horeca", "психология"
    ],
    "Management & Architecture": [
        "менеджмент", "управление", "высоконагруженные системы", "highload"
    ]
}

def extract_all_from_text(cv_text: str) -> dict:
    """
    Looks for mentions of technologies, grade and direction in the CV text.
    Returns a dictionary with all found data.
    """
    if not cv_text:
        return {"stack": "", "seniority": "", "direction": ""}
        
    text_lower = cv_text.lower()
    
    found_stack = []
    for tech in sorted(TECH_KEYWORDS):
        if "+" in tech or "#" in tech or "." in tech:
            pattern = rf"(?:^|\s|\W){re.escape(tech)}(?:$|\s|\W)"
        else:
            pattern = rf"\b{re.escape(tech)}\b"
            
        if re.search(pattern, text_lower):
            found_stack.append(tech.title())
            
    found_seniority = ""
    for kw, val in SENIORITY_KEYWORDS.items():
        if re.search(rf"\b{re.escape(kw)}\b", text_lower):
            found_seniority = val
            break 
            
    if not found_seniority:
        matches = re.finditer(
            r"(\d+)(?:[.,]\d+)?\s*(?:-[а-яa-z]+)?\s*(?:\+)?\s*(?:год|лет|года|летн[ийяегоемх]+|years?|yrs?)", text_lower
        )
        
        max_exp = 0
        for m in matches:
            years = int(m.group(1))
            
            if years < 18 and years > max_exp:
                max_exp = years

        if max_exp > 0:
            if max_exp < 2:
                found_seniority = "Junior"
            elif max_exp <= 4:
                found_seniority = "Middle"
            else:
                found_seniority = "Senior"

    found_direction = "General"  
    
    header_text = text_lower[:600]
    
    direction_scores = {dir_name: 0 for dir_name in DIRECTION_KEYWORDS}
    
    for direction, keywords in DIRECTION_KEYWORDS.items():
        for kw in keywords:
            pattern = rf"\b{re.escape(kw)}\b"
            
            if re.search(pattern, header_text):
                direction_scores[direction] += 5 
                
            elif re.search(pattern, text_lower):
                direction_scores[direction] += 1
                
    if any(direction_scores.values()):
        best_dir = max(direction_scores, key=direction_scores.get)
        
        if direction_scores[best_dir] >= 3:
            found_direction = best_dir
        else:
            found_direction = "General"
            
    return {
        "stack": ", ".join(found_stack),
        "seniority": found_seniority if found_seniority else "Not Specified",
        "direction": found_direction  
    }