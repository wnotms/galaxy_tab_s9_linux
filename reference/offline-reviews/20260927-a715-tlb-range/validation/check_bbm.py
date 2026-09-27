from pathlib import Path
import tempfile,subprocess,json
root=Path.cwd();source=(root/'.work/linux-mainline/arch/arm64/mm/mmu.c').read_text()
a=source.index('pte_t modify_prot_start_ptes(');b=source.index('\npte_t ptep_modify_prot_start(',a);original=source[a:b]
old='__flush_tlb_range(vma, addr, nr * PAGE_SIZE,';new='__flush_tlb_range(vma, addr, addr + nr * PAGE_SIZE,'
assert original.count(old)==1
with tempfile.TemporaryDirectory() as apply_dir:
 target=Path(apply_dir)/'arch/arm64/mm/mmu.c';target.parent.mkdir(parents=True);target.write_text(source)
 subprocess.run(['git','apply',str(root/'kernel/patches/diagnostic/0026-arm64-bbm-flush-range.patch')],cwd=apply_dir,check=True,capture_output=True)
 result=target.read_text();start=result.index('pte_t modify_prot_start_ptes(');end=result.index('\npte_t ptep_modify_prot_start(',start);patched=result[start:end]
 assert patched==original.replace(old,new)
preamble=r'''
#include <stdio.h>
#include <stdbool.h>
#include <stdint.h>
typedef unsigned long pte_t;
struct vm_area_struct { void *vm_mm; };
#define PAGE_SIZE 4096UL
#define ARM64_WORKAROUND_2645198 1
#define TLBF_NOWALKCACHE 8
static bool affected, accessible, executable;
static unsigned long got_start, got_end;
static unsigned calls;
static pte_t get_and_clear_ptes(void *mm, unsigned long a, pte_t *p, unsigned n) { return 0x1234; }
static bool alternative_has_cap_unlikely(int cap) { return affected; }
static bool pte_accessible(void *mm, pte_t p) { return accessible; }
static bool pte_user_exec(pte_t p) { return executable; }
static void __flush_tlb_range(struct vm_area_struct *v, unsigned long s, unsigned long e, unsigned long stride, int level, int flags) {
 got_start=s; got_end=e; calls++;
}
'''
main=r'''
int main(void) {
 unsigned long addresses[]={0,4096,8192,65536,0x7fff12345000UL};
 unsigned batches[]={1,2,16};
 unsigned failures=0, cases=0;
 struct vm_area_struct v={0};pte_t p=0;
 for(unsigned a=0;a<5;a++) for(unsigned n=0;n<3;n++)
 for(unsigned flags=0;flags<8;flags++) {
  affected=flags&1; accessible=flags&2; executable=flags&4;
  calls=0;got_start=got_end=0;
  pte_t ret=modify_prot_start_ptes(&v,addresses[a],&p,batches[n]);
  bool flush=affected&&accessible&&executable;
  if(ret!=0x1234 || calls!=flush || (flush && (got_start!=addresses[a] || got_end-got_start!=batches[n]*PAGE_SIZE))) failures++;
  cases++;
 }
 printf("cases=%u failures=%u\n",cases,failures);return failures?1:0;
}
'''
results=[]
with tempfile.TemporaryDirectory() as t:
 for name,fn in [('pinned',original),('backport',patched)]:
  p=Path(t)/(name+'.c');p.write_text(preamble+fn+main);binary=Path(t)/name
  subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Wno-unused-parameter',str(p),'-o',str(binary)],check=True,capture_output=True)
  r=subprocess.run([str(binary)],capture_output=True,text=True);results.append({'variant':name,'status':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
assert results[0]['status']==1 and 'failures=0' not in results[0]['stdout']
assert results[1]['status']==0 and 'cases=120 failures=0' in results[1]['stdout']
print(json.dumps({'scope':'actual extracted modify_prot_start_ptes with mocked TLB sink, not hardware erratum or stall reproduction','results':results},indent=2))
