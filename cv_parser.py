import re

TECH_KEYWORDS = {
    # == Programming Languages ==
    "python", "java", "c", "c++", "cpp", "c#", "csharp", "javascript", "js", "typescript", "ts",
    "sql", "php", "go", "golang", "kotlin", "matlab", "swift", "rust", "ruby", "dart", "scala", "r",
    
    # == Scripting & Shell ==
    "ecmascript", "groovy", "perl", "lua", "bash", "powershell", "vba", "emacs lisp", "gml",

    # == Frontend & UI ==
    "html", "html5", "css", "css3", "react", "react.js", "reactjs", "angular", "vue", "vue.js", "vuejs", 
    "next.js", "nextjs", "nuxt", "nuxtjs", "tailwind", "tailwind css", "material ui", "mui", "bootstrap", 
    "ant design", "primeng", "quasar", "vuetify", "shadcn", "chakra ui", "styled-components",
    "redux", "redux toolkit", "mobx", "zustand", "pinia", "vuex", "ngrx", "ngxs",
    "rtk query", "react-query", "rxjs", "axios", "graphql", "apollo",
    "sass", "scss", "less", "vite", "webpack", "npm", "yarn", "pnpm", "figma", "d3.js", "chartjs",

    # == Backend Frameworks & Runtimes ==
    "node.js", "nodejs", "express", "express.js", "nest", "nestjs", "django", "flask", "fastapi",
    "spring", "spring boot", "laravel", "symfony", "asp.net", "entity framework", "hibernate",

    # == Databases & Data/ML ==
    "postgresql", "postgres", "mysql", "mongodb", "mongo", "redis", "elasticsearch", "clickhouse",
    "mssql", "sql server", "oracle", "db2", "nosql", "cassandra", "mariadb", "sqlite",
    "spark", "airflow", "kafka", "hadoop", "dbt", "luigi", "redshift", "bigquery", "snowflake",
    "pytorch", "tensorflow", "scikit-learn", "sklearn", "mlflow", "catboost", "xgboost", "pandas", "numpy",

    # == DevOps, Cloud & IaC ==
    "aws", "gcp", "azure", "digital ocean", "digitalocean",
    "docker", "docker compose", "podman", "kubernetes", "k8s", "helm", "kustomize", "istio", "openshift",
    "terraform", "terragrunt", "cloudformation", "bicep", "pulumi", "ansible", "chef", "puppet", 
    "gitlab ci", "github actions", "jenkins", "azure devops", "bitbucket pipelines", "teamcity", "argocd",
    "nginx", "apache", "tomcat", "iis",
    "rabbitmq", "activemq", "sonarqube", "snyk", "trivy",

    # == Monitoring & Logging ==
    "grafana", "prometheus", "zabbix", "datadog", "influxdb", "new relic", "splunk",
    "elk", "efk", "logstash", "kibana", "fluentd", "loki", "promtail", "graylog",

    # == System Analysis & Methodologies ==
    "bpmn", "bpmn 2.0", "uml", "erd", "dfd", "swagger", "rest", "rest api", "soap",
    "json", "xml", "jira", "confluence", "miro", "draw.io", "lucidchart",
    "agile", "scrum", "kanban", "safe", "waterfall",

    # == Testing ==
    "jest", "cypress", "playwright", "vitest", "mocha", "jasmine", "karma", 
    "selenium", "appium", "postman", "jmeter",

    # == OS & Virtualization ==
    "windows", "linux", "ubuntu", "macos", "centos", "debian", "fedora",
    "virtualbox", "vagrant", "vmware", "kvm", "hyper-v", "lxc"
}

SENIORITY_KEYWORDS = {
    "junior": "Junior", "джуниор": "Junior", "младший": "Junior",
    "middle": "Middle", "мидл": "Middle",
    "senior": "Senior", "сеньор": "Senior", "старший": "Senior",
    "lead": "Lead", "лид": "Lead", "ведущий": "Lead"
}

DIRECTION_KEYWORDS = {
    "backend": "Backend", "бэкенд": "Backend", "back-end": "Backend",
    "frontend": "Frontend", "фронтенд": "Frontend", "front-end": "Frontend",
    "dwh": "DWH", "data warehouse": "DWH", "дата инженер": "DWH",
    "devops": "DevOps", "девопс": "DevOps",
    "ml": "ML", "machine learning": "ML", "машинное обучение": "ML",
    "qa": "QA", "тестировщик": "QA", "testing": "QA"
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
            
    found_direction = ""
    for kw, val in DIRECTION_KEYWORDS.items():
        if re.search(rf"\b{re.escape(kw)}\b", text_lower):
            found_direction = val
            break
            
    return {
        "stack": ", ".join(found_stack),
        "seniority": found_seniority,
        "direction": found_direction
    }