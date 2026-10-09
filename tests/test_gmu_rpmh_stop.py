"""Run the actual prepared GMU stop/shutdown C functions with mock registers."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'.work/build/linux-src-x710-charging/drivers/gpu/drm/msm/adreno/a6xx_gmu.c'


def function(text,name):
    start=re.search(r'(?m)^static void '+name+r'\([^;]+?\)\n\{',text).start()
    brace=text.index('{',start)
    depth=1;end=brace+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]


SHIM=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
typedef uint32_t u32;
#define BIT(n) (1U<<(n))
#define container_of(p,t,m) ((t*)((char*)(p)-offsetof(t,m)))
enum { GMU_STATUS_FW_START, GMU_STATUS_PDC_SLEEP, GMU_STATUS_OOB_PERF_SET };
enum { REG_A6XX_GMU_RSCC_CONTROL_REQ=1, REG_A6XX_GPU_RSCC_RSC_STATUS0_DRV0,
 REG_A6XX_GMU_CM3_SYSRESET, REG_A6XX_GPU_GMU_AO_GPU_CX_BUSY_STATUS,
 REG_A6XX_GPU_GMU_AO_GPU_CX_BUSY_STATUS2 };
enum { GMU_OOB_GPU_SET, GMU_OOB_PERFCOUNTER_SET };
#define A6XX_GPU_GMU_AO_GPU_CX_BUSY_STATUS_GPUBUSYIGNAHB BIT(0)
struct msm_gpu { bool needs_hw_init; };
struct adreno_gpu;
struct ops { void (*bus_halt)(struct adreno_gpu*,bool); };
struct adreno_gpu { struct msm_gpu base; struct ops* funcs; };
struct a6xx_gmu { unsigned long status; void* dev; };
struct a6xx_gpu { struct a6xx_gmu gmu; struct adreno_gpu base; bool hung; };
static int events[64], nr, errors, polls, rscc_ret, idle_ret, notify_ret, busy_ret, forced;
static u32 poll_mask;
static bool family840;
static bool test_and_clear_bit(int n,unsigned long*p) { bool v=(*p>>n)&1;*p&=~(1UL<<n);return v; }
static void set_bit(int n,unsigned long*p) { *p|=1UL<<n; }
static bool adreno_is_a840(struct adreno_gpu*p) {(void)p;return family840;}
static void gmu_write(struct a6xx_gmu*g,int reg,int value) {(void)g;assert(nr<64);events[nr++]=1000+reg*10+value;}
#define gmu_poll_timeout_rscc(g,r,val,cond,period,timeout) ((void)(g),(void)(r),assert((period)==100),assert((timeout)==10000),(val)=UINT32_MAX,poll_mask=(cond),polls++,rscc_ret)
#define gmu_poll_timeout(g,r,val,cond,period,timeout) ((void)(g),(void)(r),(void)(period),(void)(timeout),(val)=0,(void)(cond),busy_ret)
#define DRM_DEV_ERROR(...) do { errors++; } while (0)
static int a6xx_gmu_set_oob(struct a6xx_gmu*g,int n){(void)g;(void)n;return 0;}
static void a6xx_gmu_clear_oob(struct a6xx_gmu*g,int n){(void)g;(void)n;}
static int a6xx_gmu_wait_for_idle(struct a6xx_gmu*g){(void)g;return idle_ret;}
static int a6xx_gmu_notify_slumber(struct a6xx_gmu*g){(void)g;events[nr++]=600;return notify_ret;}
static void a6xx_hfi_stop(struct a6xx_gmu*g){(void)g;events[nr++]=400;}
static void a6xx_gmu_irq_disable(struct a6xx_gmu*g){(void)g;events[nr++]=300;}
static void a6xx_gmu_force_off(struct a6xx_gmu*g){(void)g;forced++;}
static void bus_halt(struct adreno_gpu*g,bool hung){(void)g;(void)hung;events[nr++]=500;}
'''
MAIN=r'''
static int at(int value) {for(int i=0;i<nr;i++)if(events[i]==value)return i;return -1;}
int main(int argc,char**argv) {
 assert(argc==2);int test=atoi(argv[1]);
 struct ops ops={bus_halt};struct a6xx_gpu gpu={0};gpu.base.funcs=&ops;
 if(test==1){a6xx_rpmh_stop(&gpu.gmu);assert(nr==0&&polls==0&&gpu.gmu.status==0);return 0;}
 gpu.gmu.status=BIT(GMU_STATUS_FW_START);
 if(test<=5){
  if(test==4)family840=true;
  if(test==5)rscc_ret=1;
  a6xx_rpmh_stop(&gpu.gmu);
  assert(nr==2&&events[0]==1011&&events[1]==1010&&polls==1);
  assert(!(gpu.gmu.status&BIT(GMU_STATUS_FW_START)));
  assert(gpu.gmu.status&BIT(GMU_STATUS_PDC_SLEEP));
  assert(poll_mask==(test==4?BIT(30):BIT(16)));assert(errors==(test==5));
  if(test==3){a6xx_rpmh_stop(&gpu.gmu);assert(nr==2&&polls==1);}
 } else {
  if(test==7)idle_ret=1;
  if(test==8)notify_ret=1;
  a6xx_gmu_shutdown(&gpu.gmu);
  if(test==6){
   assert(forced==0&&polls==1);
   assert(at(400)<at(300)&&at(300)<at(1031)&&at(1031)<at(1011)&&at(1011)<at(1010));
   assert(gpu.gmu.status&BIT(GMU_STATUS_PDC_SLEEP));
  } else {assert(forced==1&&polls==0&&at(1031)==-1&&at(1011)==-1);}
 }
 return 0;
}
'''


class GmuRpmhNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.is_file():
            raise RuntimeError('prepared kernel source is required; no skip')
        source=SOURCE.read_text()
        cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup)
        c=Path(cls.tmp.name)/'actual-gmu.c'
        c.write_text(SHIM+'\n'+function(source,'a6xx_rpmh_stop')+'\n'+function(source,'a6xx_gmu_shutdown')+'\n'+MAIN)
        cls.exe=c.with_suffix('')
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-pie','-no-pie',str(c),'-o',str(cls.exe)],check=True,capture_output=True)

    def run_case(self,n):
        r=subprocess.run([str(self.exe),str(n)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
    def test_no_firmware_start_does_not_write(self):self.run_case(1)
    def test_started_firmware_retracts_votes_and_marks_sleep(self):self.run_case(2)
    def test_stop_is_idempotent(self):self.run_case(3)
    def test_upstream_a840_ack_bit_preserved(self):self.run_case(4)
    def test_timeout_reports_and_clears_request(self):self.run_case(5)
    def test_normal_shutdown_resets_cm3_before_rpmh_stop(self):self.run_case(6)
    def test_idle_failure_uses_existing_force_off_path(self):self.run_case(7)
    def test_slumber_failure_uses_existing_force_off_path(self):self.run_case(8)


if __name__=='__main__':unittest.main()
