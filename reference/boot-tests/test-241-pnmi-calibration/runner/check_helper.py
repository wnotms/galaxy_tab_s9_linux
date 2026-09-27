from pathlib import Path
import subprocess,tempfile,json,hashlib
source=Path('out/test241/gts9_pnmi_test.c').read_text()
a=source.index('static bool enable;');b=source.index('\nstatic int gts9_pnmi_sender(');functions=source[a:b]
preamble=r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
typedef uint64_t u64;typedef uint32_t u32;typedef int atomic_t;
#define ATOMIC_INIT(x) x
#define module_param(...)
#define module_param_string(...)
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define smp_load_acquire(p) (*(p))
#define smp_store_release(p,v) (*(p)=(v))
#define NSEC_PER_SEC 1000000000ULL
#define noinline __attribute__((noinline))
#define pr_emerg(...) ((void)0)
struct pt_regs { unsigned long pc,pmr,pstate; };
static unsigned cpu,disabled_count,restored_count,clock_calls;
static bool irq_off,delivering,auto_nmi,late_nmi,stopping;
static u64 fake_clock;
static struct pt_regs regs={.pc=0x12345678,.pmr=0x80,.pstate=5};
static unsigned raw_smp_processor_id(void){return cpu;}
static bool in_nmi(void){return delivering;}
static bool arch_irqs_disabled_flags(unsigned long f){return f==0x80;}
static unsigned long instruction_pointer(struct pt_regs *r){return r->pc;}
static bool kthread_should_stop(void){return stopping;}
static void usleep_range(int a,int b){fake_clock+=10000000;}
static void cpu_relax(void){}
static void preempt_disable(void){}
static void preempt_enable(void){}
static u64 ktime_get_mono_fast_ns(void);
void gts9_pnmi_test_observe(struct pt_regs *);
static void restore(unsigned long f){irq_off=false;restored_count++;if(late_nmi){delivering=true;gts9_pnmi_test_observe(&regs);delivering=false;}}
#define local_irq_save(f) do{(f)=0xf0;irq_off=true;disabled_count++;}while(0)
#define local_irq_restore(f) restore(f)
'''
main=r'''
static u64 ktime_get_mono_fast_ns(void){
 if(++clock_calls>20000)abort();fake_clock+=1000000;
 if(auto_nmi && irq_off && holding && !delivering && !observed){delivering=true;gts9_pnmi_test_observe(&regs);delivering=false;}
 return fake_clock;
}
#define CHECK(x) do{if(!(x)){fprintf(stderr,"failed line %d: %s\n",__LINE__,#x);return 1;}}while(0)
static void reset(void){
 enable=true;holding=false;observed=false;seen_nmi=false;seen_irq_disabled=false;receiver_done=false;sender_ready=true;
 setup_error=0;seen_pc=0;start_ns=end_ns=seen_ns=0;cpu=0;disabled_count=restored_count=clock_calls=0;
 irq_off=delivering=auto_nmi=late_nmi=stopping=false;fake_clock=1000000000;
}
int main(void){
 reset();auto_nmi=true;gts9_pnmi_masked_region(NULL);
 CHECK(receiver_done&&!holding&&!irq_off&&observed&&seen_nmi&&seen_irq_disabled);
 CHECK(seen_pc==regs.pc&&seen_ns>=start_ns&&seen_ns<=end_ns);
 CHECK(end_ns-start_ns>=200000000&&end_ns-start_ns<=210000000);
 CHECK(disabled_count==1&&restored_count==1);
 reset();late_nmi=true;gts9_pnmi_masked_region(NULL);
 CHECK(receiver_done&&!observed&&disabled_count==1&&restored_count==1&&!holding);
 reset();sender_ready=false;gts9_pnmi_masked_region(NULL);
 CHECK(receiver_done&&setup_error==-ETIMEDOUT&&!disabled_count&&fake_clock<6100000000ULL);
 reset();stopping=true;gts9_pnmi_masked_region(NULL);
 CHECK(receiver_done&&setup_error==-ETIMEDOUT&&!disabled_count);
 reset();holding=true;cpu=1;gts9_pnmi_test_observe(&regs);CHECK(!observed);
 cpu=0;enable=false;gts9_pnmi_test_observe(&regs);CHECK(!observed);
 enable=true;holding=false;gts9_pnmi_test_observe(&regs);CHECK(!observed);
 holding=true;delivering=true;gts9_pnmi_test_observe(&regs);CHECK(observed&&seen_nmi);
 unsigned long saved=seen_pc;regs.pc++;gts9_pnmi_test_observe(&regs);CHECK(seen_pc==saved);
 reset();holding=true;gts9_pnmi_test_observe(NULL);CHECK(observed&&!seen_pc&&!seen_irq_disabled&&!seen_nmi);
 puts("6 scenarios passed: in-window, late, timeout, stop, guards/duplicate, null/non-NMI");return 0;
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'check.c';p.write_text(preamble+functions+main);exe=Path(d)/'check'
 c=subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Wno-unused-parameter','-Wno-unused-variable','-Wno-misleading-indentation',str(p),'-o',str(exe)],capture_output=True,text=True)
 assert c.returncode==0,c.stderr
 r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=5);assert r.returncode==0,r.stderr
 print(json.dumps({'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'scope':'actual helper receiver and observer with mocked clock/IRQ; not hardware proof','compile_stderr':c.stderr,'status':r.returncode,'stdout':r.stdout},indent=2))
