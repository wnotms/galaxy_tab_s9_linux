/* The actual bounded observer header, with no listener/device access. */
#include <assert.h>
#include "rpc-return-trace.h"

int main(void)
{
    unsigned char input[4096];
    memset(input, 0x7b, sizeof(input));
    for (unsigned i=0; i<2000; i++)
        rpc_trace("rx",i,1,1,0,0,sizeof(input),input);
    for (unsigned i=0; i<sizeof(input); i++) assert(input[i]==0x7b);
    return 0;
}
