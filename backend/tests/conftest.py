import os
import sys
import types
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.environ["DATABASE_URL"] = "sqlite://"


class _Expression:
    def is_not(self, _value):
        return self

    def in_(self, _value):
        return self

    def __ne__(self, _value):
        return self


class _Model:
    id = name = cv_url = embedding = direction = created_at = department = _Expression()


database_db = types.ModuleType("database.db")
database_db.Base = types.SimpleNamespace(metadata=types.SimpleNamespace(create_all=lambda **_: None))
database_db.SessionLocal = lambda: None
database_db.engine = object()
database_models = types.ModuleType("database.models")
for model_name in (
    "Candidate",
    "Submission",
    "Vacancy",
    "TelegramVacancy",
    "TelegramChannelState",
):
    setattr(database_models, model_name, type(model_name, (_Model,), {}))
sys.modules["database.db"] = database_db
sys.modules["database.models"] = database_models

sqlalchemy = types.ModuleType("sqlalchemy")
sqlalchemy.text = lambda statement: statement
sqlalchemy.func = types.SimpleNamespace(
    length=lambda *_: _Expression(), count=lambda *_: _Expression()
)
sqlalchemy.or_ = lambda *_: _Expression()
sys.modules["sqlalchemy"] = sqlalchemy

numpy = types.ModuleType("numpy")
numpy.float32 = float
numpy.array = lambda value, **_: value
numpy.frombuffer = lambda *_args, **_kwargs: []
sys.modules["numpy"] = numpy

requests = types.ModuleType("requests")
requests.RequestException = type("RequestException", (Exception,), {})
requests.Timeout = type("Timeout", (requests.RequestException,), {})
requests.ConnectionError = type("ConnectionError", (requests.RequestException,), {})
sys.modules["requests"] = requests

google_errors = types.ModuleType("googleapiclient.errors")
google_errors.HttpError = type("HttpError", (Exception,), {})
sys.modules["googleapiclient"] = types.ModuleType("googleapiclient")
sys.modules["googleapiclient.errors"] = google_errors

background = types.ModuleType("apscheduler.schedulers.background")
background.BackgroundScheduler = type("BackgroundScheduler", (), {})
sys.modules["apscheduler"] = types.ModuleType("apscheduler")
sys.modules["apscheduler.schedulers"] = types.ModuleType("apscheduler.schedulers")
sys.modules["apscheduler.schedulers.background"] = background

# Importing the production embedding service loads the transformer model. API
# contract tests replace it with a deterministic lightweight module.
embeddings = types.ModuleType("services.embeddings")
embeddings.embed = lambda text: [0.0]
embeddings.cosine_similarity = lambda left, right: 0.0
embeddings.model = types.SimpleNamespace(encode=lambda blocks: [[0.0] for _ in blocks])
sys.modules["services.embeddings"] = embeddings

service_stubs = {
    "services.google_docs": {"get_doc_text": lambda *_: ""},
    "services.google_sheets": {
        "sync_candidates_from_cloud": lambda *_: {},
        "sync_vacancies_from_cloud": lambda *_args, **_kwargs: {},
    },
    "services.cv_parser": {"extract_all_from_text": lambda *_: {}},
    "services.matcher": {"calculate_match_score": lambda *_: 0},
    "services.tg_scraper": {"fetch_tg_channel_posts": lambda *_args, **_kwargs: []},
}
for module_name, attributes in service_stubs.items():
    module = types.ModuleType(module_name)
    for name, value in attributes.items():
        setattr(module, name, value)
    sys.modules[module_name] = module
