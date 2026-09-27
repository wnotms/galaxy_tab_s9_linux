#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
typedef unsigned char u8;
#define __init
#define LA_CPUS 8
#define WRITE_ONCE(x,v) ((x)=(v))
#define pr_emerg(...) ((void)0)
#define of_machine_is_compatible(...) (++board_calls,1)
#define generate_random_uuid(...) (++uuid_calls)
#define tracepoint_synchronize_unregister() ((void)0)
static bool requested,active;
static char capture_id[37];
static int nr_cpu_ids=8,regs,unregs,uuid_calls,board_calls;
#define register_trace_csd_queue_cpu(...) (++regs,0)
#define unregister_trace_csd_queue_cpu(...) (++unregs)
#define register_trace_csd_function_entry(...) (++regs,0)
#define unregister_trace_csd_function_entry(...) (++unregs)
#define register_trace_csd_function_exit(...) (++regs,0)
#define unregister_trace_csd_function_exit(...) (++unregs)
#define register_trace_ipi_raise(...) (++regs,0)
#define unregister_trace_ipi_raise(...) (++unregs)
#define register_trace_ipi_entry(...) (++regs,0)
#define unregister_trace_ipi_entry(...) (++unregs)
#define register_trace_ipi_exit(...) (++regs,0)
#define unregister_trace_ipi_exit(...) (++unregs)
#define register_trace_rcu_stall_warning(...) (++regs,0)
#define unregister_trace_rcu_stall_warning(...) (++unregs)
static int __init la_setup(char *arg)
{
	requested = !strcmp(arg, "1");
	return 1;
}
static int __init la_init(void)
{
	u8 uuid[16];
	int ret;

	if (!requested)
		return 0;
	if (!of_machine_is_compatible("samsung,gts9wifi") || nr_cpu_ids != LA_CPUS)
		return -ENODEV;
	generate_random_uuid(uuid);
	snprintf(capture_id, sizeof(capture_id), "%pUb", uuid);
	/* Registration can update static keys; do it once, before claiming ready. */
	ret = register_trace_csd_queue_cpu(la_queue, NULL);
	if (ret) return ret;
	ret = register_trace_csd_function_entry(la_csd_entry, NULL);
	if (ret) goto undo_queue;
	ret = register_trace_csd_function_exit(la_csd_exit, NULL);
	if (ret) goto undo_csd_entry;
	ret = register_trace_ipi_raise(la_raise, NULL);
	if (ret) goto undo_csd_exit;
	ret = register_trace_ipi_entry(la_entry, NULL);
	if (ret) goto undo_raise;
	ret = register_trace_ipi_exit(la_exit, NULL);
	if (ret) goto undo_entry;
	ret = register_trace_rcu_stall_warning(la_stall, NULL);
	if (ret) goto undo_exit;
	WRITE_ONCE(active, true);
	pr_emerg("GTS9_LA_READY id=%s ns=%llu schema=1 events=6 complete_history=0\n",
		 capture_id, ktime_get_mono_fast_ns());
	return 0;
undo_exit:
	unregister_trace_ipi_exit(la_exit, NULL);
undo_entry:
	unregister_trace_ipi_entry(la_entry, NULL);
undo_raise:
	unregister_trace_ipi_raise(la_raise, NULL);
undo_csd_exit:
	unregister_trace_csd_function_exit(la_csd_exit, NULL);
undo_csd_entry:
	unregister_trace_csd_function_entry(la_csd_entry, NULL);
undo_queue:
	unregister_trace_csd_queue_cpu(la_queue, NULL);
	tracepoint_synchronize_unregister();
	return ret;
}

int main(void) {
 const char *disabled[]={"0","false","garbage"};
 for(int i=0;i<3;i++) {
  requested=true; if(la_setup((char *)disabled[i])!=1 || requested) return 1;
  if(la_init()!=0 || regs || unregs || uuid_calls || board_calls || active || capture_id[0]) return 2;
 }
 if(la_setup("1")!=1 || !requested || la_init()!=0) return 3;
 if(regs!=7 || unregs || uuid_calls!=1 || board_calls!=1 || !active) return 4;
 puts("disabled path: no board/UUID/probe activity; enabled control: seven probes");
 return 0;
}
