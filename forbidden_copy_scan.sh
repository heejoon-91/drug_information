#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-.}"

echo "[scan] root: ${ROOT_DIR}"

grep -RInE \
  '추천 성분|추천 제품|가장 안전|복용 가능|드셔도 됩니다|먹어도 됩니다|대체약|대체 선택지|제품 후보|증상-성분 매핑|복약 가이드|안전한 성분' \
  --include='*.html' --include='*.py' --include='*.md' \
  "${ROOT_DIR}" || true
