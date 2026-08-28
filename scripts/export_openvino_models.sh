#!/bin/sh
set -eu

OUTPUT_DIR="${OPENVINO_OUTPUT_DIR:-/output}"

export_model() {
    model_id="$1"
    task="$2"
    destination="$3"

    if [ -f "$destination/openvino_model.xml" ] && [ -f "$destination/openvino_model.bin" ]; then
        echo "Reusing existing FP32 OpenVINO artifact: $destination"
        return
    fi

    if [ -e "$destination" ]; then
        echo "Refusing incomplete OpenVINO artifact directory: $destination" >&2
        exit 1
    fi

    optimum-cli export openvino \
        --model "$model_id" \
        --task "$task" \
        --library transformers \
        --weight-format fp32 \
        "$destination"
}

mkdir -p "$OUTPUT_DIR"
export_model "BAAI/bge-m3" "feature-extraction" "$OUTPUT_DIR/bge-m3"
export_model "BAAI/bge-reranker-v2-m3" "text-classification" "$OUTPUT_DIR/bge-reranker-v2-m3"

echo "FP32 OpenVINO artifacts are ready in $OUTPUT_DIR"
