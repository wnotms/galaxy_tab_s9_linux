/* Exercise the real patched apps_std callback, with fault-injected filesystem. */
#include <assert.h>
#include <stdlib.h>
#include "apps_std.c"

static int live, opened, closed, open_error, stat_error;

int hexagonfs_openat(struct hexagonfs_fd **fds, int rootfd, int dirfd,
                    const char *path)
{
    (void)fds; (void)rootfd; (void)dirfd;
    assert(!strcmp(path, "/vendor/etc/sensors/config/test.json"));
    if (open_error) return open_error;
    assert(live == 0);
    opened++; live++;
    return 7;
}

int hexagonfs_fstat(struct hexagonfs_fd **fds, int fd, struct stat *stats)
{
    (void)fds;
    assert(fd == 7 && live == 1);
    if (stat_error) return stat_error;
    memset(stats, 0, sizeof(*stats));
    stats->st_size = 0x100000003LL;
    stats->st_mode = S_IFREG | 0444;
    stats->st_mtim.tv_sec = 1640995200;
    stats->st_mtim.tv_nsec = 123;
    stats->st_atim.tv_sec = 4; stats->st_atim.tv_nsec = 5;
    stats->st_ctim.tv_sec = 6; stats->st_ctim.tv_nsec = 7;
    return 0;
}

int hexagonfs_close(struct hexagonfs_fd **fds, int fd)
{
    (void)fds;
    assert(fd == 7 && live == 1);
    live--; closed++;
    return 0;
}

static uint64_t field(const unsigned char *wire, int offset)
{
    uint64_t value;
    memcpy(&value, wire + offset, sizeof(value));
    return value;
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    struct apps_std_ctx ctx = {0};
    char path[] = "/vendor/etc/sensors/config/test.json";
    uint64_t aligned[12];
    unsigned char *wire = (unsigned char *)aligned;
    struct fastrpc_io_buffer in[] = {{0, NULL}, {sizeof(path), path}};
    struct fastrpc_io_buffer out[] = {{sizeof(aligned), aligned}};
    memset(wire, 0xa5, sizeof(aligned));
    if (!strcmp(argv[1], "open-error")) open_error = -ENOENT;
    if (!strcmp(argv[1], "stat-error") || !strcmp(argv[1], "repeat-error")) stat_error = -EIO;
    if (!strcmp(argv[1], "zero-path")) in[1].s = 0;
    if (!strcmp(argv[1], "null-path")) in[1].p = NULL;
    if (!strcmp(argv[1], "unterminated")) path[sizeof(path)-1] = 'x';
    if (!strcmp(argv[1], "short-output")) out[0].s--;
    if (!strcmp(argv[1], "null-output")) out[0].p = NULL;
    unsigned loops = !strcmp(argv[1], "repeat-error") ? 1024 : 1;
    for (unsigned i = 0; i < loops; i++) {
        uint32_t rc = apps_std_stat(&ctx, in, out);
        if (open_error || stat_error) assert(rc == AEE_EFAILED);
        else if (strcmp(argv[1], "success")) assert(rc == AEE_EBADPARM);
        else assert(rc == 0);
        if (live != 0) return 23; /* Reproduces the unpatched descriptor leak. */
    }
    assert(opened == closed);
    if (!strcmp(argv[1], "success")) {
        assert(opened == 1);
        assert(field(wire, 0) == 0);
        assert(field(wire, 40) == 0x100000003LL);
        assert(field(wire, 48) == 4 && field(wire, 56) == 5);
        assert(field(wire, 64) == 1640995200 && field(wire, 72) == 123);
        /* Qualcomm reference also uses ctime.tv_nsec in both ctime fields. */
        assert(field(wire, 80) == 7 && field(wire, 88) == 7);
    } else {
        for (unsigned i = 0; i < sizeof(aligned); i++) assert(wire[i] == 0xa5);
        if (stat_error) assert(opened == (int)loops);
        else assert(opened == 0);
    }
    return 0;
}
