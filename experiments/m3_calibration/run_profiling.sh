#!/usr/bin/env bash
# M3 calibration — Vidur compute profiling run.
#
# NOT RUN YET. Requires a GPU and approved budget (docs/m3-calibration-plan.md).
# Runs in two phases so the pilot's measured throughput sizes the full run,
# rather than a guess sizing the spend.
#
#   bash run_profiling.sh plan    # NO GPU, NO SPEND: prints exactly what would run
#   bash run_profiling.sh pilot   # ~15 min billed, sizes everything else
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
  plan)  MAX_SEQ_LEN=131072; MAX_BATCH=512 ;;   # shows the full run; executes nothing
  pilot) MAX_SEQ_LEN=32768;  MAX_BATCH=32  ;;
  full)  MAX_SEQ_LEN=131072; MAX_BATCH=512 ;;
  *) echo "usage: $0 {plan|pilot|full}" >&2; exit 2 ;;
esac

echo "=== M3 calibration: phase=$PHASE ==="
echo "  model=$MODEL device=$DEVICE tp=$TP"
echo "  max_seq_len=$MAX_SEQ_LEN max_batch=$MAX_BATCH block_size=$BLOCK_SIZE chunk=$CHUNK"
echo "  out=$OUT_DIR"

if [ "$PHASE" = "plan" ]; then
  echo
  echo "DRY RUN — nothing is executed, no GPU is touched, no charges are incurred."
  echo
  echo "The two commands the pilot/full phases would run (copy-pasteable):"
  echo
  echo "  python -m vidur.profiling.mlp.main --models $MODEL --num_gpus 1 --output_dir $OUT_DIR/mlp_raw"
  echo
  echo "  python -m vidur.profiling.attention.main --models $MODEL --num_gpus 1 \\"
  echo "      --num_tensor_parallel_workers $TP --max_seq_len $MAX_SEQ_LEN \\"
  echo "      --max_batch_size $MAX_BATCH --block_size $BLOCK_SIZE \\"
  echo "      --max_chunk_size $CHUNK --output_dir $OUT_DIR/attention_raw"
  echo
  echo "Fixed by decision, not preference:"
  echo "  block_size=$BLOCK_SIZE   forced — Vidur filters training rows on it and every shipped"
  echo "                  profile is 16 (gate G4). 512 would empty the training frame."
  echo "  num_gpus=1      sufficient even for TP>1 compute profiling; multi-GPU is"
  echo "                  only needed for collectives, which TP=1 does not use."
  echo "  no weights      the profiler uses initialize_dummy_weights / torch.randn_like,"
  echo "                  so no gated HuggingFace access and no ~16 GB download."
  echo
  echo "Then audit the result before trusting it:"
  echo "  PYTHONPATH=src python -m workload.profile_audit_cli \\"
  echo "      <produced attention.csv> --tp $TP --block-size $BLOCK_SIZE --require-context $MAX_SEQ_LEN"
  echo
  exit 0
fi

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
