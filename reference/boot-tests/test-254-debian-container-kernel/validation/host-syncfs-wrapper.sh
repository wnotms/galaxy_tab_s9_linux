#!/bin/sh
# Host environment only. Explicit-file sync is unchanged. No-argument sync
# really flushes both Linux filesystems holding repo outputs and /tmp fixtures,
# avoiding the unrelated Windows 9p global-sync request that blocked the run.
if [ "$#" -gt 0 ]; then
    exec /usr/bin/sync "$@"
fi
for path in "$GTS9_HOST_SYNCFS_REPO" /tmp; do
    printf 'syncfs %s\n' "$path" >> "$GTS9_HOST_SYNCFS_LOG"
    /usr/bin/sync -f "$path" || exit "$?"
done
