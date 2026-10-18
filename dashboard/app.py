import truststore
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from dashboard.paths import STATIC
from dashboard.routes import demo, eval_routes, metrics, overview

truststore.inject_into_ssl()  # trust the operating system's certificate store
load_dotenv()
app = FastAPI(title="ENG-05: The Enterprise Agentic Harness Model", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

app.include_router(overview.router)
app.include_router(demo.router)
app.include_router(metrics.router)
app.include_router(eval_routes.router)
