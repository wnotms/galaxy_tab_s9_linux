// SPDX-License-Identifier: GPL-2.0-only
/*
 * Persistent bring-up console for the Samsung Galaxy Tab S9 Wi-Fi (SM-X710).
 *
 * Samsung's bootloader and recovery share a 2 MiB ring in DDR named
 * sec_log_buf.  The X710 board DTS reserves it as
 *
 *	sec_log_buf_mem: sec-log@880200000 {
 *		reg = <0x8 0x80200000 0x0 0x200000>;
 *	};
 *
 * and adds a platform device that points at it.  This driver maps that
 * reservation, writes the kernel console into it in the format the Samsung
 * boot chain expects, and leaves it in place across a warm reset, so that
 * TWRP/recovery can expose the previous mainline printk stream as
 * /proc/last_kmsg:
 *
 *	Linux printk -> sec_log_buf -> warm reset -> recovery -> /proc/last_kmsg
 *
 * Evidence status (AGENT.md: do not claim hardware works because it compiles):
 *
 *   - The reserved-memory node and its address/size come from the owner's X710
 *     stock evidence recorded in reference/stock/MANIFEST.md.
 *   - The on-memory LOGM header layout below (magic, boot_count, index,
 *     previous_index, then the byte ring) is adapted from the physically
 *     validated SM-X910 port (agcarbajo/ubuntu-galaxy-tab-s9-ultra,
 *     kernel/patches/add-samsung-sec-log-console.patch and
 *     keep-sec-log-previous-index-current.patch).  No X710 stock kernel source
 *     was available to re-derive it here, so this is a bring-up adaptation
 *     from a sibling device, NOT a physically verified X710 implementation.
 *   - Confirm it on the first boot test exactly as described in
 *     docs/FIRST_BOOT_TEST.md before relying on it.
 */

#include <linux/console.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_reserved_mem.h>
#include <linux/platform_device.h>

/* "LOGM" as a little-endian u32; the tag Samsung's sec_log users look for. */
#define SEC_LOG_MAGIC	0x4d474f4c

/*
 * Header shared with the downstream sec_log_buf implementation.  Keep this
 * layout stable: recovery reads index/previous_index to bound /proc/last_kmsg.
 */
struct sec_log_header {
	u32 boot_count;
	u32 magic;
	u32 index;
	u32 previous_index;
	u8 data[];
};

struct gts9wifi_sec_log {
	struct sec_log_header *header;
	size_t data_size;
	struct console console;
};

static struct gts9wifi_sec_log *sec_log;

static void notrace gts9wifi_sec_log_write(struct console *console,
					   const char *text,
					   unsigned int count)
{
	struct gts9wifi_sec_log *log = sec_log;
	size_t first;
	u32 index;

	if (!log || !count || !log->data_size)
		return;

	/* Only the tail of an oversized chunk can still be in the ring. */
	if (count > log->data_size) {
		text += count - log->data_size;
		count = log->data_size;
	}

	index = READ_ONCE(log->header->index);
	first = min_t(size_t, count, log->data_size - index % log->data_size);
	memcpy(&log->header->data[index % log->data_size], text, first);
	if (first != count)
		memcpy(log->header->data, text + first, count - first);

	/*
	 * Match the downstream ring: index is monotonically increasing.  Keep
	 * previous_index current as well.  Samsung's boot path normally
	 * snapshots it on a firmware-driven reset, but a manual key reboot from
	 * a mainline panic bypasses that step.  Recovery uses previous_index as
	 * the length of /proc/last_kmsg, so updating it here preserves the
	 * mainline stream in both cases.
	 */
	index += count;
	WRITE_ONCE(log->header->index, index);
	WRITE_ONCE(log->header->previous_index, index);
}

static int gts9wifi_sec_log_probe(struct platform_device *pdev)
{
	struct device_node *memory_node;
	struct reserved_mem *reserved;
	struct gts9wifi_sec_log *log;
	void *memory;

	memory_node = of_parse_phandle(pdev->dev.of_node, "memory-region", 0);
	if (!memory_node)
		return dev_err_probe(&pdev->dev, -EINVAL,
				     "missing memory-region\n");

	reserved = of_reserved_mem_lookup(memory_node);
	of_node_put(memory_node);
	if (!reserved || reserved->size <= sizeof(struct sec_log_header))
		return dev_err_probe(&pdev->dev, -EINVAL,
				     "invalid sec_log_buf reservation\n");

	log = devm_kzalloc(&pdev->dev, sizeof(*log), GFP_KERNEL);
	if (!log)
		return -ENOMEM;

	/*
	 * The X710 reservation is deliberately not "no-map", so it is already
	 * covered by the linear map; memremap gives the driver an explicit
	 * mapping and keeps the shared region out of normal allocations.
	 */
	memory = devm_memremap(&pdev->dev, reserved->base, reserved->size,
			       MEMREMAP_WB);
	if (IS_ERR(memory))
		return dev_err_probe(&pdev->dev, PTR_ERR(memory),
				     "cannot map sec_log_buf\n");

	log->header = memory;
	log->data_size = reserved->size - sizeof(*log->header);

	if (READ_ONCE(log->header->magic) != SEC_LOG_MAGIC) {
		WRITE_ONCE(log->header->boot_count, 0);
		WRITE_ONCE(log->header->magic, SEC_LOG_MAGIC);
	}

	/* Remember where the previous boot stopped before restarting the ring. */
	WRITE_ONCE(log->header->boot_count,
		   READ_ONCE(log->header->boot_count) + 1);
	WRITE_ONCE(log->header->previous_index,
		   READ_ONCE(log->header->index));
	WRITE_ONCE(log->header->index, 0);

	strscpy(log->console.name, "sec_log", sizeof(log->console.name));
	log->console.write = gts9wifi_sec_log_write;
	log->console.flags = CON_ENABLED | CON_ANYTIME | CON_PRINTBUFFER;
	log->console.index = -1;

	sec_log = log;
	register_console(&log->console);
	platform_set_drvdata(pdev, log);

	dev_info(&pdev->dev, "persistent console at %pa (%zu bytes, boot %u)\n",
		 &reserved->base, (size_t)reserved->size,
		 READ_ONCE(log->header->boot_count));
	return 0;
}

static void gts9wifi_sec_log_remove(struct platform_device *pdev)
{
	struct gts9wifi_sec_log *log = platform_get_drvdata(pdev);

	unregister_console(&log->console);
	sec_log = NULL;
}

static const struct of_device_id gts9wifi_sec_log_of_match[] = {
	{ .compatible = "samsung,gts9wifi-sec-kernel-log" },
	{ }
};
MODULE_DEVICE_TABLE(of, gts9wifi_sec_log_of_match);

static struct platform_driver gts9wifi_sec_log_driver = {
	.probe = gts9wifi_sec_log_probe,
	.remove = gts9wifi_sec_log_remove,
	.driver = {
		.name = "gts9wifi-sec-kernel-log",
		.of_match_table = gts9wifi_sec_log_of_match,
	},
};
builtin_platform_driver(gts9wifi_sec_log_driver);
