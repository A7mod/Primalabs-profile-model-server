#!/bin/bash
set -euo pipefail

MODEL_DIR=${1:-/opt/app/models}
mkdir -p "$MODEL_DIR"

MODEL_URL="https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
MODEL_FILE="$MODEL_DIR/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"

echo "Downloading model to $MODEL_FILE ..."
curl -L --fail -o "$MODEL_FILE" "$MODEL_URL"
echo "Done. Size: $(du -h "$MODEL_FILE" | cut -f1)"