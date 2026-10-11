/* Exercise the qualified Fedora apps_std/HexagonFS callbacks on private files.
 * No DSP, device node, Android persist, system service or hardware access.
 */
#include <assert.h>
#include <stdint.h>
#include "apps_std.c"

int main(int argc, char **argv)
{
    assert(argc == 3);
    struct hexagonfs_dirent registry = {
        .name = "registry", .ops = &hexagonfs_mapped_ops, .u.phys = argv[2]
    };
    struct hexagonfs_dirent *children[] = { &registry, NULL };
    struct hexagonfs_dirent root = {
        .name = "", .ops = &hexagonfs_virt_dir_ops, .u.dir = children
    };
    struct apps_std_ctx ctx = {0};
    ctx.rootfd = hexagonfs_open_root(ctx.fds, &root);
    assert(ctx.rootfd == 0);
    ctx.adsp_library_dirfd = ctx.rootfd;
    char env[] = "ADSP_LIBRARY_PATH", delimiter[] = ";";
    char name[] = "/registry/group", destination[] = "/registry/renamed";
    char mode[] = "r+", append[] = "a", readonly[] = "r";
    struct fastrpc_io_buffer opened[] = {
        {0, NULL}, {sizeof(env), env}, {sizeof(delimiter), delimiter},
        {sizeof(name), name}, {sizeof(mode), mode}
    };
    if (!strcmp(argv[1], "append")) opened[4] = (struct fastrpc_io_buffer){sizeof(append), append};
    if (!strcmp(argv[1], "readonly")) opened[4] = (struct fastrpc_io_buffer){sizeof(readonly), readonly};
    uint32_t fd = UINT32_MAX;
    struct fastrpc_io_buffer open_reply[] = {{sizeof(fd), &fd}};
    assert(apps_std_fopen_with_env(&ctx, opened, open_reply) == 0);
    struct { uint32_t fd, count; } args = {fd, 3};
    char payload[] = "new";
    struct fastrpc_io_buffer written[] = {{sizeof(args), &args}, {3, payload}};
    if (!strcmp(argv[1], "short-input")) written[1].s = 2;
    struct { uint32_t count, eof; } result = {UINT32_MAX, UINT32_MAX};
    struct fastrpc_io_buffer write_reply[] = {{sizeof(result), &result}};
    uint32_t status = apps_std_fwrite(&ctx, written, write_reply);
    struct fastrpc_io_buffer closed[] = {{sizeof(fd), &fd}};
    assert(apps_std_fclose(&ctx, closed, NULL) == 0);
    uint32_t rename_status = 0;
    if (!strcmp(argv[1], "rename")) {
        uint32_t method = 33;
        struct fastrpc_io_buffer renamed[] = {
            {sizeof(method), &method}, {sizeof(name), name},
            {sizeof(destination), destination}
        };
        rename_status = apps_std_frename(&ctx, renamed, NULL);
    }
    size_t remaining = 0;
    for (size_t i = 0; i < HEXAGONFS_MAX_FD; i++) remaining += ctx.fds[i] != NULL;
    assert(remaining == 1);
    assert(hexagonfs_close(ctx.fds, ctx.rootfd) == 0);
    printf("{\"status\":%u,\"written\":%u,\"eof\":%u,\"rename_status\":%u,\"remaining\":%zu}\n",
           status, result.count, result.eof, rename_status, remaining);
    return 0;
}
