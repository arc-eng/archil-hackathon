#!/usr/bin/env bash
# Golden sandbox setup (runs as root once per golden version): runtimes and tools every app build needs.
set -e
npm install -g @anthropic-ai/claude-code >/dev/null 2>&1
mkdir -p /home/node/apps /home/node/bin /home/node/template/public
