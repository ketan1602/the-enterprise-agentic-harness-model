from fastapi import HTTPException

from scenario.llm import config_error


def require_key() -> None:
    """The scenario runs against a live model, so every run needs a key and an endpoint."""
    if error := config_error():
        raise HTTPException(status_code=400, detail=error)
