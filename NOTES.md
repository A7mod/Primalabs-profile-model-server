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