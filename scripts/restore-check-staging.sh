#!/bin/sh
set -eu
exec python -m app.operations.backup restore-check
