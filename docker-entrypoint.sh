#!/bin/sh
set -e

# A freshly mounted volume at /data (e.g. a Railway/Docker persistent
# volume) arrives owned by root, which overrides whatever ownership the
# image set at build time. Reclaim it for the runtime user before
# dropping root, so SQLite can actually create files there.
if [ "$(id -u)" = '0' ]; then
    mkdir -p /data
    chown -R appuser:appuser /data
    exec gosu appuser "$@"
fi

exec "$@"
