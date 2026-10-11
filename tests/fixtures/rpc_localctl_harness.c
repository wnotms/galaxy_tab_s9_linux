/* Actual Fedora callbacks; no device, RPC, filesystem or hardware operation. */
#include <assert.h>
#include <stdarg.h>
#include "listener.c"
#include "localctl.c"

static unsigned acknowledged;

int fastrpc2(const struct fastrpc_function_def_interp2 *def,
             int fd, uint32_t target, ...)
{
    (void)fd;
    assert(def->msg_id==4 && target==ADSP_LISTENER_HANDLE);
    va_list ap;
    va_start(ap,target);
    assert(va_arg(ap,uint32_t)==17);
    assert(va_arg(ap,uint32_t)==20);
    assert(va_arg(ap,uint32_t)==0);
    assert(va_arg(ap,void *)==NULL);
    uint32_t *rctx=va_arg(ap,uint32_t *);
    uint32_t *handle=va_arg(ap,uint32_t *);
    uint32_t *sc=va_arg(ap,uint32_t *);
    uint32_t *length=va_arg(ap,uint32_t *);
    assert(va_arg(ap,uint32_t)==256);
    void *buffer=va_arg(ap,void *);
    uint32_t packed[] = {4,0,4};
    memcpy(buffer,packed,sizeof(packed));
    *rctx=18; *handle=1; *sc=REMOTE_SCALARS_MAKE(3,1,0); *length=sizeof(packed);
    acknowledged++;
    va_end(ap);
    return 0;
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    struct fastrpc_interface iface[] = {
        { .name="apps_remotectl" }, { .name="apps_std" }, { .name="apps_mem" }
    };
    struct fastrpc_interface *ifaces[] = { &iface[0], &iface[1], &iface[2] };
    struct remotectl_ctx ctx = { .n_ifaces=3, .ifaces=ifaces };
    const char *name = argv[1];
    uint32_t numbers[] = { strlen(name)+1, 255 }, result[] = { 0xfefefefe, 0xfefefefe };
    unsigned char text[255];
    memset(text, 0xfe, sizeof(text));
    struct fastrpc_io_buffer in[] = {{ sizeof(numbers), numbers }, { strlen(name)+1, (void *)name }};
    struct fastrpc_io_buffer out[] = {{ sizeof(result), result }, { sizeof(text), text }};
    uint32_t status = localctl_open(&ctx, in, out);
    for (unsigned i=0; i<sizeof(text); i++) assert(text[i]==0);
    uint32_t unsupported = 0;
    struct fastrpc_io_buffer *omitted = NULL;
    int fatal = invoke_requested_procedure(3, ifaces, UINT32_MAX,
        REMOTE_SCALARS_MAKE(0,2,1), &unsupported, in, &omitted);
    assert(!fatal && unsupported==AEE_EUNSUPPORTED && omitted==NULL);
    uint32_t rctx=17, handle=UINT32_MAX, sc=REMOTE_SCALARS_MAKE(0,2,1);
    struct fastrpc_io_buffer *decoded=NULL;
    assert(return_for_next_invoke(3,unsupported,&rctx,&handle,&sc,
        omitted,&decoded,0,UINT32_MAX)==0);
    assert(acknowledged==1 && decoded!=NULL && decoded[0].s==4);
    iobuf_free(1,decoded);
    printf("{\"status\":%u,\"handle\":%u,\"error\":%u,\"text_zeroed\":true,"
        "\"unsupported_status\":%u,\"fatal\":%d,\"unsupported_encoded_bytes\":0}\n",
        status,result[0],result[1],unsupported,fatal);
    return 0;
}
