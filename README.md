# Profile-Aware Model Container

> **A note on time:** this was scoped as a ~3 hour assignment. In
> practice it took considerably longer, spread across a compressed
> window, working solo. Two real bugs surfaced during testing (a
> llama.cpp concurrency crash, and a bash `pipefail` issue in my own
> test script) that took real debugging time beyond the core build.
> I'm noting this because I'd rather be upfront about the actual
> effort than imply this was dashed off in the estimated window.


A containerized TinyLlama-1.1B chat server exposing an OpenAI-compatible
API, with three deploy-time profiles (`throughput`, `latency`, `balanced`)
that produce real, observable differences in runtime behavior.

## How to build

```bash
docker build -t profile-model-server .
```

Model weights (TinyLlama-1.1B-Chat, Q4_K_M GGUF, ~670MB) are downloaded
during the build so the container has zero network dependency at
runtime. First build takes ~11 minutes (mostly compiling
llama-cpp-python); subsequent builds are cached unless `app/` changes.
Final image: 1.42GB content size.

## How to run each profile

```bash
docker run -d -p 8000:8000 -e PROFILE=balanced   profile-model-server
docker run -d -p 8000:8000 -e PROFILE=throughput profile-model-server
docker run -d -p 8000:8000 -e PROFILE=latency    profile-model-server
```

If `PROFILE` is unset, it defaults to `balanced`. An invalid value
(e.g. `PROFILE=bogus`) fails fast at container start with a clear
error listing valid profiles — nothing partially starts.

## Example curl invocations

```bash
curl http://localhost:8000/v1/health/live
curl http://localhost:8000/v1/health/ready
curl http://localhost:8000/v1/models
curl http://localhost:8000/v1/profiles

curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Say hello in one word."}],"max_tokens":20}'
```

## Example OpenAI Python client invocation

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")

resp = client.chat.completions.create(
    model="TinyLlama-1.1B-Chat-v1.0",
    messages=[{"role": "user", "content": "Say hello in one word."}],
    max_tokens=20,
)
print(resp.choices[0].message.content)
```

Verified working against the running container — see `test_openai_client.py`.

## How to verify a profile is actually applied

1. `docker exec <container> list-profiles` shows the active profile
   and its resolved parameters.
2. `GET /v1/profiles` returns the same info over HTTP.
3. **Behavioral proof**: sending 3 concurrent requests under `latency`
   (max_concurrent_requests=1) returns 1x `200` and 2x `429`. The
   same test under `throughput` (max_concurrent_requests=8) returns
   3x `200`. This proves the profile gates real request handling, not
   just metadata.

## Tradeoffs and decisions

- **llama.cpp / GGUF over vLLM/transformers**: CPU-only requirement
  made llama.cpp the pragmatic choice — no CUDA dependency, small
  image, fast cold start.
- **Model baked into the image at build time**, not pulled at
  container start, trading image size for a network-independent,
  deterministic container.
- **Two-layer concurrency control**: an `asyncio.Semaphore` sized to
  `max_concurrent_requests` gates admission (this is what produces
  the profile-dependent 429 behavior), and a separate `asyncio.Lock`
  serializes the actual inference call underneath it. The lock was
  added after discovering llama-cpp-python's C++ core isn't
  thread-safe for concurrent calls on one model instance — sending 3
  concurrent requests under `throughput` (limit=8) initially crashed
  the process with GGML assertion failures, since multiple threads
  raced on internal KV-cache state. The semaphore alone gave the
  *appearance* of per-profile concurrency; the lock makes it *safe*
  without removing the observable admission-control difference
  between profiles.
- **Fail-fast over silent fallback**: an invalid `PROFILE` value
  exits immediately with a clear error rather than silently using a
  default — chosen because a misconfigured deploy failing loudly at
  startup is far cheaper to debug than one serving traffic under the
  wrong config.
- **What I'd do differently with more time**: replace the hard 429
  rejection with a bounded queue + timeout (better UX under bursty
  load), tune `n_threads` per-profile (currently identical across
  all three), and add Prometheus metrics for queue depth and
  tokens/sec.

## Known blockers / assumptions

- Tested on Docker Desktop / WSL2, CPU-only, no GPU passthrough.
- If your environment can't reach HuggingFace at build time, download
  the GGUF file manually and adjust `scripts/download_model.sh` to
  `COPY` a local file instead of `curl`-ing it.
- `libgomp1` must be explicitly installed in the runtime stage —
  llama-cpp-python's compiled library needs GNU OpenMP at runtime,
  which isn't pulled in automatically by the slim base image even
  though it's present in the builder stage.

  ## Not covered / left thin

- **Logging**: only uvicorn's default access logs are present. No
  structured application-level logging (model load time, profile
  resolution events, request-level tracing beyond the generic 500
  handler). Given more time this would be the first thing I'd add.
- **Security defaults beyond non-root user**: the container runs as
  a non-root user, but I did not add a read-only root filesystem,
  drop Linux capabilities, or set `no-new-privileges`. These are
  common hardening steps I'd add for a real production deployment.
- **Graceful shutdown**: relies on uvicorn/FastAPI's default SIGTERM
  handling (lifespan shutdown phase). This wasn't explicitly tested
  with a `docker stop` against an in-flight request — I'm trusting
  the framework default rather than having verified it myself.
- **Docker-level resource limits**: no `--memory`/`--cpus` constraints
  were set or tested. Profile-level tuning (n_ctx, n_batch, n_threads)
  is the only resource control implemented.