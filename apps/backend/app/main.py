import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.core.config import settings
from app.core.database import create_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_schema:
        await create_schema()
    if settings.auto_seed_agent_templates:
        try:
            from app.core.database import SessionLocal
            from app.services.templates_seed import seed_agent_templates

            async with SessionLocal() as db:
                summary = await seed_agent_templates(db)
            print(
                "agent_templates_seed "
                f"created={summary.get('created')} updated={summary.get('updated')} "
                f"skipped={summary.get('skipped')} official={summary.get('total_official')}",
                flush=True,
            )
        except Exception as exc:  # never block API boot on seed failure
            print(f"agent_templates_seed_failed: {exc}", flush=True)
    yield


app = FastAPI(
    title="Agents Morf API",
    description=(
        "Provider-neutral, multi-tenant autonomous AI agent API with memory, knowledge, "
        "training examples, tools and an OpenAI-compatible chat endpoint."
    ),
    version="0.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(router, prefix=settings.api_prefix)
