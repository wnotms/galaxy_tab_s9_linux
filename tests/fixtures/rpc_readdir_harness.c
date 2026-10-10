/* Include the actual callback, not a Python/C copy of its implementation.
 * Only the FS boundary is mocked. Linker GC discards all other callbacks. */
#include <assert.h>
#include <stdlib.h>
#include <stddef.h>
#define HEXAGONRPC_BUILD_METHOD_DEFINITIONS 1
#include "apps_std.c"

static const char *mode;
static unsigned calls;

int hexagonfs_readdir(struct hexagonfs_fd **fds, int fd, size_t size, char *name)
{
    (void)fds;
    assert(fd == 3 && size == 255);
    calls++;
    if (!strcmp(mode, "error"))
        return -EIO;
    if (!strcmp(mode, "eof") || !strcmp(mode, "repeat"))
        name[0] = '\0';
    else if (!strcmp(mode, "max-name")) {
        memset(name, 'x', 254);
        name[254] = '\0';
    } else
        strcpy(name, "registry.config");
    return 0;
}

int main(int argc, char **argv)
{
    assert(argc == 3);
    const bool original = !strcmp(argv[1], "original");
    mode = argv[2];
    uint64_t fd = 3;
    struct apps_std_ctx ctx = {0};
    union { uint64_t alignment; unsigned char bytes[280]; } reply;
    struct fastrpc_io_buffer in = {.p=&fd, .s=8}, out = {.p=reply.bytes, .s=264};
    unsigned attempts = !strcmp(mode, "repeat") ? 512 : 1;
    uint32_t result = 0;
    for (unsigned i=0; i<attempts; i++) {
        memset(reply.bytes, 0xa5, sizeof(reply.bytes));
        if (!strcmp(mode, "short-in")) in.s = 4;
        if (!strcmp(mode, "long-in")) in.s = 12;
        if (!strcmp(mode, "short-out")) out.s = 260;
        if (!strcmp(mode, "long-out")) out.s = 268;
        if (!strcmp(mode, "null-in")) in.p = NULL;
        if (!strcmp(mode, "null-out")) out.p = NULL;
        result = apps_std_readdir(&ctx, &in, &out);
        for (size_t j=264; j<sizeof(reply.bytes); j++) assert(reply.bytes[j] == 0xa5);
    }
    bool invalid = strstr(mode, "-in") || strstr(mode, "-out");
    unsigned residue = 0;
    uint32_t eof = 0, inode = 0;
    memcpy(&inode, reply.bytes, 4);
    memcpy(&eof, reply.bytes+260, 4);
    for (size_t i=5; i<259; i++) residue += reply.bytes[i] != 0;
    if (invalid) {
        assert(!original && result == AEE_EBADPARM && calls == 0);
        for (size_t i=0; i<264; i++) assert(reply.bytes[i] == 0xa5);
    } else if (!strcmp(mode, "error")) {
        assert(result == AEE_EFAILED && calls == 1);
        if (!original) for (size_t i=0; i<264; i++) assert(reply.bytes[i] == 0);
    } else {
        assert(result == 0 && calls == attempts && inode == 0);
        if (!strcmp(mode, "eof") || !strcmp(mode, "repeat")) {
            assert(eof == 1 && reply.bytes[4] == 0);
            assert(original ? residue == 254 : residue == 0);
        } else {
            assert(eof == 0);
            if (!strcmp(mode, "max-name")) {
                assert(strlen((char *)reply.bytes+4) == 254);
                for (size_t i=4; i<258; i++) assert(reply.bytes[i] == 'x');
            } else assert(!strcmp((char *)reply.bytes+4, "registry.config"));
        }
        if (!original) assert(reply.bytes[259] == 0);
    }
    printf("{\"status\":%u,\"calls\":%u,\"eof\":%u,\"inode\":%u,"
           "\"tail_nonzero\":%u,\"padding\":%u}\n",
           result, calls, eof, inode, residue, reply.bytes[259]);
    return 0;
}
