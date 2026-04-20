#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_NAME="algo-trump-era-delta.service"
UNIT_SOURCE="$PROJECT_ROOT/ops/systemd/$UNIT_NAME"
UNIT_TARGET="$HOME/.config/systemd/user/$UNIT_NAME"

mkdir -p "$HOME/.config/systemd/user"
cp "$UNIT_SOURCE" "$UNIT_TARGET"

systemctl --user daemon-reload
systemctl --user enable "$UNIT_NAME"

cat <<EOF
Installed $UNIT_NAME to $UNIT_TARGET

Start:
  systemctl --user start $UNIT_NAME

Status:
  systemctl --user status $UNIT_NAME

Logs:
  journalctl --user -u $UNIT_NAME -f
EOF
