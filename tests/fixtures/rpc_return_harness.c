/* Exercise the real listener/codec; only the device ioctl boundary is replaced. */
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include "listener.c"

static unsigned calls;
static int large_input, transport_failure;
static unsigned char incoming[324];
static size_t incoming_size;

static void put32(unsigned char *p, uint32_t value)
{
    memcpy(p, &value, sizeof(value));
}

int fastrpc2(const struct fastrpc_function_def_interp2 *def,
             int fd, uint32_t handle, ...)
{
    va_list ap;
    (void)fd;
    assert(handle == ADSP_LISTENER_HANDLE);
    va_start(ap, handle);
    if (def->msg_id == 5) {
        assert(va_arg(ap, uint32_t) == 9 + calls);
        assert(va_arg(ap, uint32_t) == 256);
        uint32_t *required = va_arg(ap, uint32_t *);
        assert(va_arg(ap, uint32_t) == incoming_size - 256);
        void *buffer = va_arg(ap, void *);
        memcpy(buffer, incoming + 256, incoming_size - 256);
        *required = incoming_size;
        va_end(ap);
        return 0;
    }
    assert(def->msg_id == 4);
    assert(va_arg(ap, uint32_t) == (calls ? 10 : 0));
    assert(va_arg(ap, uint32_t) == (calls ? 0 : UINT32_MAX));
    uint32_t bytes = va_arg(ap, uint32_t);
    const unsigned char *returned = va_arg(ap, void *);
    if (calls) {
        uint32_t value;
        assert(bytes == 28);
        memcpy(&value, returned, 4); assert(value == 8);
        memcpy(&value, returned + 8, 4); assert(value == 4);
        memcpy(&value, returned + 12, 4); assert(value == 1);
        memcpy(&value, returned + 16, 4); assert(value == 4);
        assert(!memcmp(returned + 24, "abcd", 4));
    } else {
        assert(bytes == 0 && returned == NULL);
    }
    uint32_t *rctx = va_arg(ap, uint32_t *);
    uint32_t *target_handle = va_arg(ap, uint32_t *);
    uint32_t *sc = va_arg(ap, uint32_t *);
    uint32_t *length = va_arg(ap, uint32_t *);
    assert(va_arg(ap, uint32_t) == 256);
    void *buffer = va_arg(ap, void *);
    if (calls++ && transport_failure) {
        errno = EIO;
        va_end(ap);
        return -1;
    }
    *rctx = 9 + calls;
    *target_handle = 1;
    *sc = REMOTE_SCALARS_MAKE(4, 2, 2);
    *length = incoming_size;
    memcpy(buffer, incoming, incoming_size > 256 ? 256 : incoming_size);
    va_end(ap);
    return 0;
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    unsigned char guard[RPC_TRACE_FRAME_MAX + 1];
    memset(guard, 0x7b, sizeof(guard));
    if (!strcmp(argv[1], "frame-limit")) {
        rpc_trace("rx", 0, 1, 1, 0, 0, sizeof(guard), guard);
        rpc_trace("rx", 1, 1, 1, 0, 0, 1, guard);
        return 0;
    }
    if (!strcmp(argv[1], "null-frame")) {
        rpc_trace("rx", 0, 1, 1, 0, 0, 1, NULL);
        return 0;
    }
    if (!strcmp(argv[1], "budget")) {
        for (unsigned i = 0; i < 1000; i++)
            rpc_trace("rx", i, 1, 1, 0, 0, 4096, guard);
        for (unsigned i = 0; i < sizeof(guard); i++) assert(guard[i] == 0x7b);
        return 0;
    }
    large_input = !strcmp(argv[1], "large");
    transport_failure = !strcmp(argv[1], "transport-error");
    put32(incoming, 4); put32(incoming + 8, 7);
    put32(incoming + 12, large_input ? 300 : 0);
    if (large_input) memset(incoming + 16, 0x5a, 300);
    incoming_size = large_input ? 316 : 16;
    /* Qualcomm pack_out_lens follows pack_in_bufs, without alignment. */
    put32(incoming + incoming_size, 8);
    put32(incoming + incoming_size + 4, 4);
    incoming_size += 8;
    uint32_t rctx = 0, handle = 0, sc = 0;
    uint32_t numbers[] = {4, 1};
    struct fastrpc_io_buffer returned[] = {{sizeof(numbers), numbers}, {4, "abcd"}};
    struct fastrpc_io_buffer *decoded = NULL;
    assert(return_for_next_invoke(3, UINT32_MAX, &rctx, &handle, &sc,
                                 NULL, &decoded, 0, 0) == 0);
    assert(decoded[0].s == 4 && decoded[1].s == (large_input ? 300 : 0));
    if (!large_input) assert(decoded[1].p == NULL);
    iobuf_free(2, decoded);
    decoded = NULL;
    int ret = return_for_next_invoke(3, 0, &rctx, &handle, &sc,
                                    returned, &decoded, 1, handle);
    assert(ret == (transport_failure ? -1 : 0));
    assert(numbers[0] == 4 && numbers[1] == 1 && !memcmp(returned[1].p, "abcd", 4));
    if (!ret) iobuf_free(2, decoded);
    return 0;
}
