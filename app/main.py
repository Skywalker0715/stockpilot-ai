 # entrypoint FastAPI application
 
from fastapi import FastAPI
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from app.routes import route
from app import config


app = FastAPI(title="LLM -> Google Maps Backend")

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda r, e: JSONResponse(status_code=429, content={"detail": "rate limit exceeded"})
)

# Register routes
app.include_router(route.router)