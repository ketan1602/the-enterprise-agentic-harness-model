from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from dashboard.routes import demo, eval_routes, metrics, overview

app = FastAPI(title="Article 02 — Beyond the Model", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")
app.include_router(overview.router)
app.include_router(demo.router)
app.include_router(metrics.router)
app.include_router(eval_routes.router)
