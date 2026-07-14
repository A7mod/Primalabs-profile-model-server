import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import resolve_active_profile

STATE = {
    "model": None,
    "ready": False,
    "profile_name": None,
    "profile_params": None,
    "manifest": None,
    "semaphore": None,
    "inference_lock": None,
}


def load_model():
    from llama_cpp import Llama

    name, params, manifest = resolve_active_profile()
    model_cfg = manifest["model"]
    model_path = f"models/{model_cfg['file']}"

    llm = Llama(
        model_path=model_path,
        n_ctx=params["n_ctx"],
        n_batch=params["n_batch"],
        n_threads=params["n_threads"],
        verbose=False,
    )

    STATE["model"] = llm
    STATE["profile_name"] = name
    STATE["profile_params"] = params
    STATE["manifest"] = manifest
    STATE["semaphore"] = asyncio.Semaphore(params["max_concurrent_requests"])
    STATE["inference_lock"] = asyncio.Lock()
    STATE["ready"] = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, load_model)
    yield


app = FastAPI(lifespan=lifespan)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    max_tokens: int | None = None
    temperature: float | None = None


@app.get("/v1/health/live")
async def health_live():
    return {"status": "live"}


@app.get("/v1/health/ready")
async def health_ready():
    if not STATE["ready"]:
        return JSONResponse(status_code=503, content={"status": "loading"})
    return {"status": "ready"}


@app.get("/v1/profiles")
async def profiles():
    if not STATE["ready"]:
        raise HTTPException(status_code=503, detail="model not loaded yet")
    return {
        "active_profile": STATE["profile_name"],
        "active_params": STATE["profile_params"],
        "available_profiles": STATE["manifest"]["profiles"],
    }


@app.get("/v1/models")
async def models():
    model_name = STATE["manifest"]["model"]["name"] if STATE["manifest"] else "unknown"
    return {
        "object": "list",
        "data": [{"id": model_name, "object": "model", "created": int(time.time()), "owned_by": "local"}],
    }


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    if not STATE["ready"]:
        raise HTTPException(status_code=503, detail="model not loaded yet")

    params = STATE["profile_params"]
    max_tokens = req.max_tokens or params["default_max_tokens"]
    temperature = req.temperature if req.temperature is not None else params["temperature"]

    sem: asyncio.Semaphore = STATE["semaphore"]
    if sem.locked() and sem._value == 0:
        raise HTTPException(
            status_code=429,
            detail=f"max_concurrent_requests ({params['max_concurrent_requests']}) exceeded",
        )

    async with sem:
        async with STATE["inference_lock"]:
                loop = asyncio.get_event_loop()
                messages = [{"role": m.role, "content": m.content} for m in req.messages]
                result = await loop.run_in_executor(
                    None,
                    lambda: STATE["model"].create_chat_completion(
                        messages=messages, max_tokens=max_tokens, temperature=temperature
                    ),
                )

    result["id"] = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    result["model"] = STATE["manifest"]["model"]["name"]
    return result


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})