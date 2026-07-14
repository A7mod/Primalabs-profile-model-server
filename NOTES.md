# Build Notes — Profile-Aware Model Container

## Phase 1: Manifest + config loader
- Designed manifest with 3 profiles (throughput/latency/balanced), each
  varying n_ctx, n_batch, n_threads, max_concurrent_requests.
- config.py resolves active profile from PROFILE env var, defaults to
  manifest's default_profile if unset.

## Phase 2: Model loading (llama-cpp-python)
Errors hit:
1. `externally-managed-environment` on `pip install` — Debian/Ubuntu
   blocks system-wide pip installs (PEP 668). Fixed with a venv.
2. `ensurepip is not available` — missing `python3.12-venv` package.
   Fixed: `sudo apt install python3.12-venv`.
- Model itself (TinyLlama-1.1B Q4_K_M GGUF) loaded and ran correctly
  on first real attempt once the environment was sorted — no model-
  level issues.

## Phase 3: FastAPI server
Errors hit:
1. `FileNotFoundError: model_manifest.yaml` — ran uvicorn from inside
   app/, but manifest path is relative to CWD, and manifest lives in
   project root, not app/. Fixed by running uvicorn from project root.
2. Import error risk avoided by switching `from config import ...` to
   `from app.config import ...` once running as a package (`app.server`)
   from root, instead of a bare module from inside app/.
- All 5 endpoints verified manually via curl: health/live, health/ready,
  /v1/models, /v1/profiles, /v1/chat/completions — all returned correct
  OpenAI-shaped responses.

## Time spent so far
~2.5h from environment setup through working local API.

## Next: Phase A (entrypoint validation + list-profiles CLI)

## Phase A: Entrypoint validation + list-profiles CLI
- validate_profile.py: fails fast on bad PROFILE, exit code 1, clear
  stderr message listing valid profiles. Tested pass + fail case.
- list_profiles.py: uses sys.path.insert + bare `from config import`
  (not `from app.config import` like server.py) since it runs
  standalone via `docker exec`, not as part of the app package.
  Deliberate inconsistency, not an oversight - worth noting in
  tradeoffs section.
- Both verified working locally before touching Docker.

## Phase B: Dockerfile
- Multi-stage build: builder (compiles llama-cpp-python, downloads model)
  + runtime (slim, non-root user).
- Image: 3.09GB disk / 1.42GB content size.
- Build time: ~11 min first build (pip install 449s, model download 72s),
  much faster on rebuild due to Docker layer caching.

Errors hit:
1. `OSError: libgomp.so.1: cannot open shared object file` on container
   startup. Root cause: llama-cpp-python's compiled library needs
   GNU OpenMP runtime (libgomp), which was present in the builder stage
   (pulled in by build-essential) but NOT in the slim runtime stage -
   multi-stage builds only carry over what you explicitly COPY, so a
   dependency needed at runtime but only implicitly present at build
   time silently doesn't make it to the final image. Fixed by
   explicitly `apt-get install libgomp1` in the runtime stage.

Verified in-container (balanced profile):
- health/live, health/ready, /v1/profiles, /v1/chat/completions all
  correct.
- list-profiles CLI works via `docker exec`.
- Invalid PROFILE fails fast with clear error before server starts.


## Phase C: Verify profiles + concurrency proof

Verified /v1/profiles reports correct active_profile + params for
throughput, latency, and balanced.

Concurrency test: fired 3 simultaneous requests.
- latency (limit=1): 1x 200, 2x 429 - correct, admission control works.
- throughput (limit=8) FIRST ATTEMPT: crashed the whole process with
  GGML_ASSERT failures (logits != nullptr, index out of bounds).

Root cause: llama-cpp-python's underlying C++ library is not
thread-safe for concurrent calls on a single model instance. The
semaphore correctly ADMITTED multiple concurrent requests, but each
admitted request ran inference on its own thread-pool thread, and
multiple threads calling into llama.cpp at once corrupted shared
internal state (KV cache indexing) - hence the crash. This only
surfaced under throughput (limit=8) because latency (limit=1) never
had more than one request in flight to race.

Fix: added an asyncio.Lock around the actual model inference call,
nested inside the existing semaphore block. Semaphore still does
admission control (real, provable per-profile behavior - the 429s),
lock ensures correctness by serializing actual execution regardless
of profile. This is a known constraint of single-instance llama.cpp,
not a workaround hiding a design flaw - documented as a tradeoff in
the README.

Re-verified after fix: throughput now handles 3 concurrent requests
as 3x 200, no crash.