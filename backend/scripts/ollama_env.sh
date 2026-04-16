#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Ollama performance environment variables — AnjalArivaan / Takshashila
# Source this file BEFORE starting `ollama serve`:
#
#   source backend/scripts/ollama_env.sh && ollama serve
#
# Or add these exports to ~/.bashrc / ~/.zshrc for permanent effect.
# ─────────────────────────────────────────────────────────────────────

# Listen address — 0.0.0.0 so docker containers (api, etc.) can reach it
# via host.docker.internal on Mac and the host IP on Linux.
export OLLAMA_HOST="0.0.0.0:11434"

# Number of inference slots — concurrent requests Ollama will serve.
export OLLAMA_NUM_PARALLEL=4

# Maximum models to keep resident in VRAM at once.
# 2 = the chat model + the embedding model (BAAI/bge-m3) co-resident.
export OLLAMA_MAX_LOADED_MODELS=2

# Maximum number of queued requests before Ollama returns 503.
export OLLAMA_MAX_QUEUE=512

# CPU threads for KV-cache management and token sampling.
# Should match the num_thread value baked into the Modelfile.
export OLLAMA_NUM_THREADS=8

# How long to keep a model in VRAM after the last request.
# "24h" = 24 hours.  "-1" = indefinite (never unload).
export OLLAMA_KEEP_ALIVE=24h

# FlashAttention — faster prefill on supported NVIDIA / AMD GPUs.
# Set to 0 if you encounter errors on unsupported hardware.
export OLLAMA_FLASH_ATTENTION=1

# 🔴 Priority 1 — KV cache quantisation.
# q8_0 = 8-bit  (minimal quality loss, ~30% VRAM saving)
# q4_0 = 4-bit  (more aggressive saving, slight quality drop)
# unset / 'f16' = full precision
export OLLAMA_KV_CACHE_TYPE=q8_0

echo "✓ Ollama perf env active —"
echo "  NUM_PARALLEL=${OLLAMA_NUM_PARALLEL}  MAX_LOADED=${OLLAMA_MAX_LOADED_MODELS}  THREADS=${OLLAMA_NUM_THREADS}  KEEP_ALIVE=${OLLAMA_KEEP_ALIVE}  FLASH_ATTN=${OLLAMA_FLASH_ATTENTION}  KV_CACHE=${OLLAMA_KV_CACHE_TYPE}"
