#!/usr/bin/env bash
# IPC Messenger - Universidad Simon Bolivar
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt --quiet
python3 main.py
