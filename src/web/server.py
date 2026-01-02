"""Server entry point for web API."""

import uvicorn

from src.web.api import app

if __name__ == "__main__":
    uvicorn.run(
        "src.web.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

