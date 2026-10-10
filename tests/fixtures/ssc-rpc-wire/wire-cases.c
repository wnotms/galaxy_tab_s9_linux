/* Independent wire vector from Qualcomm listener_buf.h's non-empty-only alignment. */
#include <string.h>
#include "iobuffer.h"

int main(void)
{
	/* empty, "abc", empty, "x", empty: 29 bytes, no trailing padding */
	const unsigned char expected[] = {
		0,0,0,0, 3,0,0,0, 'a','b','c', 0,0,0,0,
		1,0,0,0, 0,0,0,0,0, 'x', 0,0,0,0
	};
	struct fastrpc_io_buffer input[] = {
		{0, NULL}, {3, "abc"}, {0, NULL}, {1, "x"}, {0, NULL}
	};
	struct fastrpc_decoder_context *ctx;
	struct fastrpc_io_buffer *decoded;
	unsigned char output[sizeof(expected) + 1];
	size_t i;
	int failed = 0;

	if (outbufs_calculate_size(5, input) != sizeof(expected))
		return 10;
	memset(output, 0xa5, sizeof(output));
	outbufs_encode(5, input, output);
	if (memcmp(output, expected, sizeof(expected)) || output[sizeof(expected)] != 0xa5)
		return 11;
	ctx = inbuf_decode_start(5U << 16);
	if (!ctx)
		return 12;
	for (i = 0; i < sizeof(expected); i++) {
		if (inbuf_decode(ctx, 1, &expected[i]))
			return 13;
	}
	if (!inbuf_decode_is_complete(ctx))
		return 14;
	decoded = inbuf_decode_finish(ctx);
	for (i = 0; i < 5; i++) {
		if (decoded[i].s != input[i].s)
			failed = 15;
		else if (input[i].s && memcmp(decoded[i].p, input[i].p, input[i].s))
			failed = 16;
		else if (!input[i].s && decoded[i].p)
			failed = 17;
	}
	iobuf_free(5, decoded);
	return failed;
}
