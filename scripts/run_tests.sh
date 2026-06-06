#!/usr/bin/env bash
set -euo pipefail
pytest tests/ -v --cov=my_operator --cov-report=term-missing "$@"
