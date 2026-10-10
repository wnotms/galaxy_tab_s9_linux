/* Actual apps_std callback and HexagonFS; private host files only, no DSP.
 * Error entries inject native failures; the missing entry is real VFS ENOENT.
 */
#include <assert.h>
#include <stdint.h>
#include "apps_std.c"

static int injected_error;
static int fault_open(const void *entry, bool dir, void **data)
{
    return injected_error;
}
static void fault_close(void *data) { abort(); }

static size_t allocated(const struct apps_std_ctx *ctx)
{
    size_t count = 0;
    for (size_t i = 0; i < HEXAGONFS_MAX_FD; i++) count += ctx->fds[i] != NULL;
    return count;
}

int main(int argc, char **argv)
{
    assert(argc == 3);
    const char *mode = argv[1];
    struct hexagonfs_file_ops faults = { .from_dirent = fault_open, .close = fault_close };
    struct hexagonfs_dirent present = { .name = "present.so", .ops = &hexagonfs_mapped_ops, .u.phys = argv[2] };
    struct hexagonfs_dirent denied = { .name = "fault.so", .ops = &faults };
    struct hexagonfs_dirent *children[] = { &present, &denied, NULL };
    struct hexagonfs_dirent root = { .name = "", .ops = &hexagonfs_virt_dir_ops, .u.dir = children };
    struct apps_std_ctx ctx = {0};
    ctx.rootfd = hexagonfs_open_root(ctx.fds, &root);
    assert(ctx.rootfd == 0);
    ctx.adsp_library_dirfd = ctx.rootfd;
    ctx.adsp_avs_cfg_dirfd = ctx.rootfd;
    char env[] = "ADSP_LIBRARY_PATH", bad_env[] = "UNKNOWN_PATH";
    char delimiter[] = ";", read_mode[] = "r", write_mode[] = "w", bad_mode[] = "x";
    const char *name = "oemconfig.so";
    if (!strcmp(mode, "present") || !strcmp(mode, "readonly-write")) name = "present.so";
    if (!strcmp(mode, "permission") || !strcmp(mode, "io-error")) name = "fault.so";
    injected_error = !strcmp(mode, "permission") ? -EACCES : -EIO;
    struct fastrpc_io_buffer in[] = {
        {0, NULL}, {sizeof(env), env}, {sizeof(delimiter), delimiter},
        {strlen(name) + 1, (void *)name}, {sizeof(read_mode), read_mode}
    };
    if (!strcmp(mode, "unknown-env")) in[1] = (struct fastrpc_io_buffer){sizeof(bad_env), bad_env};
    if (!strcmp(mode, "bad-mode")) in[4] = (struct fastrpc_io_buffer){sizeof(bad_mode), bad_mode};
    if (!strcmp(mode, "readonly-write")) in[4] = (struct fastrpc_io_buffer){sizeof(write_mode), write_mode};
    if (!strcmp(mode, "missing-dir")) ctx.adsp_library_dirfd = -ENOENT;
    uint32_t result = 0xdeadbeef, rc = 0;
    struct fastrpc_io_buffer out[] = {{sizeof(result), &result}};
    unsigned loops = !strcmp(mode, "repeat-missing") ? 1024 : 1;
    for (unsigned i = 0; i < loops; i++) {
        errno = EIO; /* virtual ENOENT does not change the C library's errno */
        rc = apps_std_fopen_with_env(&ctx, in, out);
        if (!rc) {
            char buffer[32] = {0};
            assert(!strcmp(mode, "present") && allocated(&ctx) == 2);
            assert(hexagonfs_read(ctx.fds, result, sizeof(buffer), buffer) == 15);
            assert(!strcmp(buffer, "private-payload"));
            assert(hexagonfs_close(ctx.fds, result) == 0);
        } else {
            assert(result == 0xdeadbeef);
        }
        assert(allocated(&ctx) == 1);
    }
    printf("{\"case\":\"%s\",\"status\":%u,\"loops\":%u,\"remaining_fds\":%zu}\n",
           mode, rc, loops, allocated(&ctx));
    assert(hexagonfs_close(ctx.fds, ctx.rootfd) == 0);
    assert(allocated(&ctx) == 0);
    return 0;
}
