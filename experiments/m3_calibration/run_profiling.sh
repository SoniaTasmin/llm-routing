#!/usr/bin/env bash
# M3 calibration — Vidur compute profiling run.
#
# NOT RUN YET. Requires a GPU and approved budget (docs/m3-calibration-plan.md).
# Runs in two phases so the pilot's measured throughput sizes the full run,
# rather than a guess sizing the spend.
#
#   bash run_profiling.sh pilot   # ~15 min, sizes everything else
#   bash run_profiling.sh full    # only after the pilot's numbers are reviewed
#
# Writes to $OUT_DIR. Nothing is copied into simulator/vendor/ — that tree is
# immutable (simulator/vendor/PROVENANCE.md). Produced profiles land in
# calibration/ and are pointed at by config.

set -euo pipefail

PHASE="${1:-pilot}"
MODEL="${MODEL:-meta-llama/Meta-Llama-3-8B}"
DEVICE="${DEVICE:-a100}"
TP="${TP:-1}"
BLOCK_SIZE=16          # forced: every shipped profile is 16, and Vidur filters on it (gate G4)
CHUNK=4096
OUT_DIR="${OUT_DIR:-$(pwd)/calibration/${DEVICE}/${MODEL}}"

case "$PHASE" in
  pilot) MAX_SEQ_LEN=32768;  MAX_BATCH=32  ;;
  full)  MAX_SEQ_LEN=131072; MAX_BATCH=512 ;;
  *) echo "usage: $0 {pilot|full}" >&2; exit 2 ;;
esac

echo "=== M3 calibration: phase=$PHASE ==="
echo "  model=$MODEL device=$DEVICE tp=$TP"
echo "  max_seq_len=$MAX_SEQ_LEN max_batch=$MAX_BATCH block_size=$BLOCK_SIZE chunk=$CHUNK"
echo "  out=$OUT_DIR"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || {
  echo "no GPU visible; this script cannot run here" >&2; exit 1; }

mkdir -p "$OUT_DIR"
START=$(date +%s)

# MLP first: seconds, and it fails fast if the environment is wrong.
python -m vidur.profiling.mlp.main \
    --models "$MODEL" \
    --num_gpus 1 \
    --output_dir "$OUT_DIR/mlp_raw"

python -m vidur.profiling.attention.main \
    --models "$MODEL" \
    --num_gpus 1 \
    --num_tensor_parallel_workers "$TP" \
    --max_seq_len "$MAX_SEQ_LEN" \
    --max_batch_size "$MAX_BATCH" \
    --block_size "$BLOCK_SIZE" \
    --max_chunk_size "$CHUNK" \
    --output_dir "$OUT_DIR/attention_raw"

ELAPSED=$(( $(date +%s) - START ))
echo "=== phase=$PHASE finished in ${ELAPSED}s ==="

ATT=$(find "$OUT_DIR/attention_raw" -name attention.csv | head -1)
echo "rows produced: $(( $(wc -l < "$ATT") - 1 ))   elapsed: ${ELAPSED}s"
echo "throughput   : $(python3 -c "print(f'{($(wc -l < "$ATT")-1)/$ELAPSED:.1f} rows/s')")"
echo
echo "Now audit it before trusting it:"
echo "  python -m workload.profile_audit_cli $ATT --tp $TP --block-size $BLOCK_SIZE"
