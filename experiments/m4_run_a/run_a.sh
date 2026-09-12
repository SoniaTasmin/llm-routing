#!/usr/bin/env bash
# M4 Run A — bounded integration check. No fit, no GPU, no spend.
#
# Enforced limits (user-authorised 2026-09-12):
#   - only the compatible cached Llama-2-7b predictor  (REQUIRE_CACHE aborts otherwise)
#   - <=128 deterministic requests fitting a 4,096-token total-context budget
#   - 10 min total wall clock
#   - 5.5 GB process-tree RSS, killed on breach
#   - full log to file, never `tail`
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIDUR="$ROOT/.spike/vidur-canary"          # holds the M1 cache/ directory
TRACE="$ROOT/experiments/m4_run_a/run_a_trace.csv"
LOGDIR="$ROOT/experiments/m4_run_a/logs"
WALL_LIMIT=600                              # 10 minutes, total for BOTH runs
RSS_LIMIT_KB=$((5500 * 1024))               # 5.5 GB

mkdir -p "$LOGDIR"
START=$(date +%s)

run_once () {
  local tag="$1" log="$LOGDIR/run_${1}.log"
  local remaining=$(( WALL_LIMIT - ($(date +%s) - START) ))
  if [ "$remaining" -le 10 ]; then
    echo "ABORT: wall-clock budget exhausted before $tag"; return 124
  fi

  ( cd "$VIDUR" && WANDB_MODE=disabled timeout "$remaining" \
      ./.venv/bin/python -m vidur.main \
        --request_generator_config_type trace \
        --trace_request_generator_config_trace_file "$TRACE" \
        --cluster_config_num_replicas 4 \
        --replica_config_device a100 \
        --replica_config_model_name meta-llama/Llama-2-7b-hf \
        --replica_config_tensor_parallel_size 1 \
        --replica_scheduler_config_type vllm_v1 \
        --cache_config_enable_prefix_caching \
        --cache_config_block_size 16 \
        --global_scheduler_config_type lor \
        --random_forest_execution_time_predictor_config_cache_mode require_cache \
        --metrics_config_output_dir "$LOGDIR/out_${tag}" \
        --no-metrics_config_write_json_trace \
        --no-metrics_config_enable_chrome_trace \
        --no-metrics_config_store_plots ) > "$log" 2>&1 &
  local pid=$!

  local peak=0
  while kill -0 "$pid" 2>/dev/null; do
    local rss
    rss=$(ps -o rss= --ppid "$pid" -p "$pid" 2>/dev/null | awk '{s+=$1} END {print s+0}')
    [ "$rss" -gt "$peak" ] && peak=$rss
    if [ "$rss" -gt "$RSS_LIMIT_KB" ]; then
      echo "ABORT: process-tree RSS ${rss}KB exceeded limit ${RSS_LIMIT_KB}KB"
      pkill -P "$pid" 2>/dev/null; kill -9 "$pid" 2>/dev/null; return 137
    fi
    sleep 1
  done
  wait "$pid"; local rc=$?
  echo "${tag}: exit=${rc} peak_rss_kb=${peak}"
  return $rc
}

echo "=== Run A: integration check (NOT a feasibility or fidelity result) ==="
run_once 1; RC1=$?
run_once 2; RC2=$?
echo "=== elapsed $(( $(date +%s) - START ))s (limit ${WALL_LIMIT}s) ==="
exit $(( RC1 + RC2 ))
