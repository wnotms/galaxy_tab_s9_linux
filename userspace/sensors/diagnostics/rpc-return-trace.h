/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Test-only observation of the actual listener2 bytes, never PD/SSC policy. */
#ifndef GTS9_RPC_RETURN_TRACE_H
#define GTS9_RPC_RETURN_TRACE_H

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RPC_TRACE_FRAME_MAX 8192U
#define RPC_TRACE_TOTAL_MAX (512U * 1024U)

static void rpc_trace(const char *phase, uint64_t seq, uint32_t rctx,
                      uint32_t handle, uint32_t sc, int64_t status,
                      size_t bytes, const void *data)
{
    static int enabled = -1;
    static size_t total;
    static int stopped;
    const unsigned char *p = data;
    const char digits[] = "0123456789abcdef";
    char line[2 * RPC_TRACE_FRAME_MAX + 256];
    int prefix;
    size_t length, i;

    if (enabled < 0) {
        const char *value = getenv("HEXAGONRPC_RETURN_TRACE");
        enabled = value && !strcmp(value, "1");
    }
    if (!enabled || stopped)
        return;
    if (bytes > RPC_TRACE_FRAME_MAX || (bytes && !data)) {
        fprintf(stderr, "RPCRETURN_LIMIT seq=%" PRIu64 " reason=frame\n", seq);
        stopped = 1;
        return;
    }
    prefix = snprintf(line, sizeof(line),
                      "RPCRETURN seq=%" PRIu64 " phase=%s rctx=%" PRIu32
                      " handle=%" PRIu32 " sc=%08" PRIx32
                      " status=%" PRId64 " bytes=%zu hex=",
                      seq, phase, rctx, handle, sc, status, bytes);
    if (prefix < 0 || prefix >= 255) {
        fprintf(stderr, "RPCRETURN_LIMIT seq=%" PRIu64 " reason=header\n", seq);
        stopped = 1;
        return;
    }
    length = (size_t)prefix;
    for (i = 0; i < bytes; i++) {
        line[length++] = digits[p[i] >> 4];
        line[length++] = digits[p[i] & 15];
    }
    if (!bytes)
        line[length++] = '-';
    line[length++] = '\n';
    if (length > RPC_TRACE_TOTAL_MAX - total) {
        fprintf(stderr, "RPCRETURN_LIMIT seq=%" PRIu64 " reason=budget\n", seq);
        stopped = 1;
        return;
    }
    if (fwrite(line, 1, length, stderr) != length) {
        fprintf(stderr, "RPCRETURN_LIMIT seq=%" PRIu64 " reason=write\n", seq);
        stopped = 1;
        return;
    }
    total += length;
}

#endif
