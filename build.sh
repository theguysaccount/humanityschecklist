#!/bin/sh
# Builds the site into docs/. The real work is in build.py.
set -e
cd "$(dirname "$0")"
python3 build.py
