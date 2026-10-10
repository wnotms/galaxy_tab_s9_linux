/* Exercise the actual rpcd.c reverse tunnel with host-only RPC/FS stand-ins.
 * No open/ioctl/device call survives linker section collection. */
#include <assert.h>
#include <stdlib.h>
#include <stdarg.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>

static void fixture_free(void *ptr);
#define free fixture_free
#define main rpcd_unused_main
#define HEXAGONRPC_BUILD_METHOD_DEFINITIONS 1
#include "rpcd.c"
#undef main
#undef free

static const char *mode;
static unsigned opens, registers, closes, loops, locals_closed, allocations;
static bool alive, alive_at_loop;
static void *context;
static char events[8192];
static size_t count;
static struct fastrpc_interface iface[3];
static struct hexagonfs_dirent root;

static void event(char c)
{
    assert(count + 1 < sizeof(events));
    events[count++] = c;
    events[count] = '\0';
}

static void fixture_free(void *ptr)
{
    if (ptr && ptr == context) {
        assert(alive);
        alive = false;
        allocations--;
        context = NULL;
    }
    free(ptr);
}

struct fastrpc_context *fastrpc_create_context(int fd, uint32_t handle)
{
    assert(fd == 7 && handle == 41 && !alive);
    struct fastrpc_context *ctx = malloc(sizeof(*ctx));
    assert(ctx);
    ctx->fd = fd;
    ctx->handle = handle;
    context = ctx;
    alive = true;
    allocations++;
    return ctx;
}

int fastrpc2(const struct fastrpc_function_def_interp2 *def, int fd, uint32_t handle, ...)
{
    assert(fd == 7 && handle == REMOTECTL_HANDLE);
    va_list ap;
    va_start(ap, handle);
    int transport = 0;
    if (def == &remotectl_open_def) {
        opens++;
        event('O');
        int len = va_arg(ap, int);
        const char *name = va_arg(ap, const char *);
        uint32_t *h = va_arg(ap, uint32_t *);
        int32_t *status = va_arg(ap, int32_t *);
        assert(len == (int)strlen(name) + 1 && !strcmp(name, "adsp_default_listener"));
        *h = 41;
        *status = !strcmp(mode, "open-dsp-error") ? AEE_EFAILED : 0;
        if (!strcmp(mode, "open-transport-error")) {
            errno = EIO;
            transport = -1;
        }
    } else {
        assert(def == &remotectl_close_def);
        closes++;
        event('C');
        assert(va_arg(ap, uint32_t) == 41 && alive);
        uint32_t *status = va_arg(ap, uint32_t *);
        *status = !strcmp(mode, "close-dsp-error") ? AEE_EFAILED : 0;
        if (!strcmp(mode, "close-transport-error")) {
            errno = EIO;
            transport = -1;
        }
    }
    va_end(ap);
    return transport;
}

int fastrpc(const struct fastrpc_function_def_interp2 *def, const struct fastrpc_context *ctx, ...)
{
    assert(def == &adsp_default_listener_register_def && alive);
    assert(ctx->fd == 7 && ctx->handle == 41);
    registers++;
    event('R');
    return !strcmp(mode, "register-error") ? AEE_EFAILED : 0;
}

struct hexagonfs_dirent *construct_root_dir(const char *prefix, const char *dsp)
{
    assert(!strcmp(prefix, "/host-only") && !strcmp(dsp, "adsp"));
    return &root;
}

struct fastrpc_interface *fastrpc_localctl_init(size_t n, struct fastrpc_interface **ifaces)
{
    assert(n == 3 && ifaces);
    return &iface[0];
}

void fastrpc_localctl_deinit(struct fastrpc_interface *p)
{
    assert(p == &iface[0]);
    event('D');
    locals_closed++;
}

struct fastrpc_interface *fastrpc_apps_std_init(struct hexagonfs_dirent *p)
{
    assert(p == &root);
    return &iface[1];
}

struct fastrpc_interface *fastrpc_apps_mem_init(int fd)
{
    assert(fd == 7);
    return &iface[2];
}

int run_fastrpc_listener(int fd, size_t n, struct fastrpc_interface **ifaces)
{
    assert(fd == 7 && n == 3 && ifaces[0] == &iface[0] &&
           ifaces[1] == &iface[1] && ifaces[2] == &iface[2]);
    loops++;
    alive_at_loop = alive;
    event('L');
    return !strcmp(mode, "loop-error") ? -1 : 0;
}

const char *aee_strerror[256] = {[AEE_EFAILED] = "host injected DSP failure"};

int main(int argc, char **argv)
{
    assert(argc == 3);
    mode = argv[2];
    unsigned repeats = !strcmp(mode, "repeat") ? 512 : 1;
    for (unsigned i = 0; i < repeats; i++) {
        /* Permit the original close-error leak to be measured separately. */
        assert(!alive);
        start_reverse_tunnel(7, "/host-only", "adsp");
        if (i + 1 < repeats)
            assert(!alive && !allocations);
    }
    printf("{\"profile\":\"%s\",\"case\":\"%s\",\"opens\":%u,"
           "\"registers\":%u,\"closes\":%u,\"loops\":%u,"
           "\"held_at_loop\":%s,\"locals_closed\":%u,"
           "\"remaining_contexts\":%u,\"events\":\"%s\"}\n",
           argv[1], mode, opens, registers, closes, loops,
           alive_at_loop ? "true" : "false", locals_closed, allocations, events);
    if (alive)
        fixture_free(context); /* host test teardown, after recording leak */
    return 0;
}
