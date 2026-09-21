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
 *
 * Boot test 1 (reference/stock/BOOT_TEST_1.md) boot-looped with an empty ring:
 * registering the console from a platform driver only happens at
 * device_initcall time, long after the failures this console exists to catch.
 * The console is therefore registered from an early_initcall now, and the
 * region can be forced from the command line with
 *
 *	gts9_sec_log=0x880200000,0x200000
 *
 * so capture does not depend on the device tree reaching Linux at all. Only
 * one registration ever happens: whichever path runs first owns the ring.
 */

#include <asm/cacheflush.h>
#include <asm/early_ioremap.h>

#include <linux/console.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/of_reserved_mem.h>
#include <linux/platform_device.h>
#include <linux/string.h>

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

/*
 * The ring is reached through a write-back mapping (both the linear map and
 * memremap(MEMREMAP_WB)), and it is read back by TWRP through *physical*
 * memory after a reset.  A reset does not clean our caches, so every write
 * that must survive has to be cleaned to the point of coherency explicitly.
 */
static void notrace gts9wifi_sec_log_flush(void *start, size_t len)
{
	dcache_clean_poc((unsigned long)start, (unsigned long)start + len);
}

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

	/*
	 * Push the new bytes and the indices out to DRAM.  The ring is mapped
	 * write-back, and recovery reads physical memory after a warm reset -
	 * a reset does not flush our caches, so without this the log that was
	 * just written is exactly the part that disappears.  This is why every
	 * capture before this fix found the ring holding only the bootloader's
	 * own (uncached) log.
	 */
	gts9wifi_sec_log_flush(log->header, sizeof(*log->header) + first);
	if (first != count)
		gts9wifi_sec_log_flush(log->header->data, count - first);
}

/*
 * Common bring-up of the ring.  Called either from the early_initcall below or
 * from the platform driver, whichever runs first; the second caller finds
 * sec_log already set and leaves the ring alone so the boot log is not reset.
 */
static int gts9wifi_sec_log_setup(phys_addr_t base, size_t size, bool early)
{
	struct gts9wifi_sec_log *log;
	void *memory;

	if (sec_log)
		return 0;
	if (!base || size <= sizeof(struct sec_log_header))
		return -EINVAL;

	log = kzalloc(sizeof(*log), GFP_KERNEL);
	if (!log)
		return -ENOMEM;

	/*
	 * The X710 reservation is deliberately not "no-map", so it is already
	 * covered by the linear map; memremap gives the driver an explicit
	 * mapping and keeps the shared region out of normal allocations.
	 */
	memory = memremap(base, size, MEMREMAP_WB);
	if (!memory) {
		kfree(log);
		return -ENOMEM;
	}

	log->header = memory;
	log->data_size = size - sizeof(*log->header);

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
	gts9wifi_sec_log_flush(log->header, sizeof(*log->header));

	strscpy(log->console.name, "sec_log", sizeof(log->console.name));
	log->console.write = gts9wifi_sec_log_write;
	log->console.flags = CON_ENABLED | CON_ANYTIME | CON_PRINTBUFFER;
	log->console.index = -1;

	sec_log = log;

	/*
	 * Registering replays the whole printk buffer through
	 * gts9wifi_sec_log_write (CON_PRINTBUFFER), so everything printed before
	 * this point - including the early arm64 banner - lands in the ring.
	 */
	register_console(&log->console);

	pr_info("gts9wifi-sec-log: persistent console at %pa (%zu bytes, boot %u, %s)\n",
		&base, size, READ_ONCE(log->header->boot_count),
		early ? "early_initcall" : "platform probe");
	return 0;
}

/*
 * gts9_sec_log=<base>[,<size>] - force the ring location from the command line
 * so capture does not depend on the device tree that Linux ends up with.
 *
 * This handler also drops a proof-of-life marker into the ring.  It runs from
 * parse_early_param() inside arm64 setup_arch(), after early_ioremap_init()
 * but before paging_init(), memory init, the device tree is unflattened and
 * any console exists.  It therefore answers the one question boot tests 1 and
 * 2 could not: did the kernel start at all?  If the marker is in the ring, the
 * image was entered and arm64 setup began; if it is absent, the kernel never
 * got that far and the fault is in the hand-off, not in a driver.
 *
 * The write is bounded (one page) and lands in the oldest end of the ring.  A
 * later, successful boot overwrites it with the real log, which is the desired
 * precedence.
 */
static phys_addr_t gts9wifi_sec_log_cmdline_base;
static phys_addr_t gts9wifi_sec_log_cmdline_size;
static bool gts9wifi_sec_log_cmdline_set;

/*
 * The ring location is fixed on this board until the command line is parsed,
 * and the early markers must not depend on anything that is not set up yet.
 */
#define GTS9_SEC_LOG_DEFAULT_BASE	0x880200000ULL

#define GTS9_SEC_LOG_MARKER_LEN	160

/*
 * Slot 0 is written from parse_early_param() (early cmdline parsed), slot 1
 * from setup_arch() before the device tree is touched, slot 2 by head.S
 * before anything at all.  Separate slots so one boot reports how far it got.
 */
static const char *const gts9wifi_sec_log_markers[] __initconst = {
	"\nGTS9-EARLY-MARKER: parse_early_param reached, cmdline parsed\n",
	"\nGTS9-SETUPARCH: arm64 setup_arch entered, before setup_machine_fdt\n",
	"\nGTS9-HEAD: kernel image executing, entry reached with MMU off\n",
};

/**
 * gts9_sec_log_early_marker() - write a proof-of-life marker into the ring
 * @slot: which marker to write (see gts9wifi_sec_log_markers[])
 * @base: ring physical base, or 0 for the board default
 *
 * Called from arch/arm64 code by the bring-up diagnostic patch.  Uses the
 * fixmap-based early mapping, which is the only way to reach the ring before
 * paging_init() has built the linear map.
 */
void __init gts9_sec_log_early_marker(unsigned int slot, phys_addr_t base)
{
	void *marker;

	if (slot >= ARRAY_SIZE(gts9wifi_sec_log_markers))
		return;
	if (!base)
		base = GTS9_SEC_LOG_DEFAULT_BASE;

	marker = early_memremap(base + sizeof(struct sec_log_header) +
				slot * 0x100, GTS9_SEC_LOG_MARKER_LEN);	if (!marker)
		return;

	memset(marker, 0, GTS9_SEC_LOG_MARKER_LEN);
	memcpy(marker, gts9wifi_sec_log_markers[slot],
	       strlen(gts9wifi_sec_log_markers[slot]));
	/*
	 * Clean before unmapping: a marker left dirty in cache is exactly the
	 * evidence that is lost when the next reset happens.
	 */
	gts9wifi_sec_log_flush(marker, GTS9_SEC_LOG_MARKER_LEN);
	early_memunmap(marker, GTS9_SEC_LOG_MARKER_LEN);
}

static int __init gts9wifi_sec_log_override(char *str)
{
	char *sep;

	if (!str || !*str)
		return -EINVAL;

	sep = strchr(str, ',');
	if (sep)
		*sep++ = '\0';

	gts9wifi_sec_log_cmdline_base = memparse(str, NULL);
	gts9wifi_sec_log_cmdline_size = sep ? memparse(sep, NULL) : 0;
	gts9wifi_sec_log_cmdline_set = true;

	gts9_sec_log_early_marker(0, gts9wifi_sec_log_cmdline_base);
	return 0;
}
early_param("gts9_sec_log", gts9wifi_sec_log_override);

static int __init gts9wifi_sec_log_early_init(void)
{
	struct device_node *np, *memory_node;
	struct resource res;
	phys_addr_t base;
	size_t size;
	int ret;

	if (gts9wifi_sec_log_cmdline_set) {
		base = gts9wifi_sec_log_cmdline_base;
		size = gts9wifi_sec_log_cmdline_size;
	} else {
		np = of_find_compatible_node(NULL, NULL,
					     "samsung,gts9wifi-sec-kernel-log");
		if (!np)
			return 0;

		memory_node = of_parse_phandle(np, "memory-region", 0);
		of_node_put(np);
		if (!memory_node)
			return 0;

		if (of_address_to_resource(memory_node, 0, &res)) {
			of_node_put(memory_node);
			return 0;
		}
		of_node_put(memory_node);

		base = res.start;
		size = resource_size(&res);
	}

	ret = gts9wifi_sec_log_setup(base, size, true);
	if (ret)
		pr_warn("gts9wifi-sec-log: early console not registered (%d)\n",
			ret);
	return 0;
}
early_initcall(gts9wifi_sec_log_early_init);

static int gts9wifi_sec_log_probe(struct platform_device *pdev)
{
	struct device_node *memory_node;
	struct reserved_mem *reserved;

	if (sec_log) {
		dev_info(&pdev->dev,
			 "ring already owned by the early console; leaving it alone\n");
		return 0;
	}

	memory_node = of_parse_phandle(pdev->dev.of_node, "memory-region", 0);
	if (!memory_node)
		return dev_err_probe(&pdev->dev, -EINVAL,
				     "missing memory-region\n");

	reserved = of_reserved_mem_lookup(memory_node);
	of_node_put(memory_node);
	if (!reserved || reserved->size <= sizeof(struct sec_log_header))
		return dev_err_probe(&pdev->dev, -EINVAL,
				     "invalid sec_log_buf reservation\n");

	return gts9wifi_sec_log_setup(reserved->base, reserved->size, false);
}

static void gts9wifi_sec_log_remove(struct platform_device *pdev)
{
	if (!sec_log)
		return;

	unregister_console(&sec_log->console);
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
