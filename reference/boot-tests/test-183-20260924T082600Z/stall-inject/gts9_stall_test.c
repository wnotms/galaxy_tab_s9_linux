// SPDX-License-Identifier: GPL-2.0-only
/*
 * gts9_stall_test - inject one controlled stall so the watchdog profile can be
 * validated end to end (stall -> detector -> panic -> panic=10 reboot ->
 * evidence) without waiting for the intermittent DPU/RPMh race.
 *
 *   insmod gts9_stall_test.ko mode=hung seconds=60
 *       a kernel thread blocks uninterruptibly on a completion that is never
 *       completed: the hung-task detector (kernel.hung_task_timeout_secs=45,
 *       kernel.hung_task_panic=1) must panic.
 *
 *   insmod gts9_stall_test.ko mode=spin seconds=25
 *       interrupts are disabled on one CPU while it spins, then re-enabled:
 *       the soft-lockup detector (kernel.softlockup_panic=1) must report
 *       "BUG: soft lockup - CPU#n stuck for Ns" and panic.  This is the shape
 *       the real X710 stall has.
 *
 * Both modes end by themselves, so a profile that fails to panic leaves a
 * working tablet rather than a wedged one.  The module changes no hardware
 * state: it only blocks or spins.
 */
#include <linux/completion.h>
#include <linux/jiffies.h>
#include <linux/kthread.h>
#include <linux/module.h>
#include <linux/ktime.h>

static int mode = 0;
module_param(mode, int, 0444);
MODULE_PARM_DESC(mode, "0 = hung task, 1 = soft lockup spin");

static unsigned int seconds = 60;
module_param(seconds, uint, 0444);
MODULE_PARM_DESC(seconds, "how long to stall");

static DECLARE_COMPLETION(gts9_never);
static struct task_struct *gts9_task;

static int gts9_stall_thread(void *unused)
{
	if (mode == 1) {
		ktime_t end = ktime_add_ms(ktime_get(), (u64)seconds * 1000);
		pr_info("gts9_stall_test: spinning with interrupts disabled for %us\n",
			seconds);
		local_irq_disable();
		while (ktime_before(ktime_get(), end))
			cpu_relax();
		local_irq_enable();
		pr_info("gts9_stall_test: spin finished\n");
	} else {
		pr_info("gts9_stall_test: blocking uninterruptibly for %us\n",
			seconds);
		wait_for_completion_timeout(&gts9_never, (u64)seconds * HZ);
		pr_info("gts9_stall_test: wait finished\n");
	}
	return 0;
}

static int __init gts9_stall_init(void)
{
	gts9_task = kthread_run(gts9_stall_thread, NULL, "gts9-stall");
	if (IS_ERR(gts9_task))
		return PTR_ERR(gts9_task);
	return 0;
}

static void __exit gts9_stall_exit(void)
{
	if (gts9_task && !IS_ERR(gts9_task))
		kthread_stop(gts9_task);
}

module_init(gts9_stall_init);
module_exit(gts9_stall_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("X710 controlled stall injector for watchdog validation");
