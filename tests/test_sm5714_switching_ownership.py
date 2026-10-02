"""Execute real battery companion/configuration/PM C with I2C faults and locks."""
import subprocess
import unittest
from pathlib import Path

import test_sm5714_charge_safety as safety
from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class SwitchingOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        safety.ChargeSafetyTests.setUpClass.__func__(cls)
        src = (ROOT / 'kernel/drivers/sm5714-battery.c').read_text()
        code = (Path(cls.temp.name) / 'charge.c').read_text().split('int main(')[0]
        code = code.replace('#include <stdbool.h>', '''#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
#include <pthread.h>
#include <string.h>
#include <stddef.h>
#define U64_MAX UINT64_MAX
static void host_lock(void *p);
static void host_unlock(void *p);
static _Thread_local int held;''')
        code = code.replace('#define mutex_lock(x) ((void)(x))', '#define mutex_lock(x) host_lock(x)')
        code = code.replace('#define mutex_unlock(x) ((void)(x))', '#define mutex_unlock(x) host_unlock(x)')
        code = code.replace('#define lockdep_assert_held(x) ((void)(x))', '#define lockdep_assert_held(x) assert(held & 2)')
        code = code.replace('static int mode, temp = 250, type, writes, temp_error;',
                            'static int mode, temp = 250, type, writes, temp_error, io, fail_at, drop_q4, drop_input, online=1;')
        code = code.replace('  (void)c;\n  if (mode == 4',
                            '  (void)c; io++; if (io == fail_at) return -EREMOTEIO;\n  if (mode == 4')
        code = code.replace('  (void)c; writes++;',
                            '  (void)c; writes++; io++; if (io == fail_at) return -EREMOTEIO;\n'
                            '  if ((drop_q4 && r == 0x13) || (drop_input && r == 0x15)) return 0;')
        code = code.replace('static int sm5714_get_online_raw(struct sm5714_battery *sm) { (void)sm; return 1; }', 'static int sm5714_get_online_raw(struct sm5714_battery *sm) { (void)sm; return online; }')
        code = code.replace('struct sm5714_battery { int chg_lock, chg, dev, psy_usb, psy_bat;',
                            'struct sm5714_battery { bool last_online; int last_status, last_capacity, last_usb_type; unsigned int poll_count; int chg_lock, chg, dev, psy_usb, psy_bat, poll_work;')
        code += r'''
struct work_struct { int dummy; };
#define to_delayed_work(x) (x)
#define container_of(x,t,m) ((t *)((char *)(x)-offsetof(t,m)))
#define msecs_to_jiffies(x) (x)
#define SM5714_CAPACITY_POLL_DIVIDER 10
#define SM5714_POLL_INTERVAL_MS 1000
static int sm5714_get_capacity(struct sm5714_battery *sm,int *v) {(void)sm;*v=52;return 0;}
#define EXPORT_SYMBOL_GPL(x)
#define power_supply_changed(x) ((void)(x))
#define dev_get_drvdata(x) ((void *)(x))
#define cancel_delayed_work_sync(x) ((void)(x))
#define schedule_delayed_work(x,y) ((void)(x),(void)(y))
typedef struct sm5714_battery device;
#define device sm5714_battery
static int sm5714_companion_lock;
static struct sm5714_battery *sm5714_companion;
static u64 sm5714_switching_issuer;
static bool sm5714_switching_blocked;
static pthread_mutex_t registry = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t charger = PTHREAD_MUTEX_INITIALIZER;
static void host_lock(void *p) {
 if (p == &sm5714_companion_lock) {assert(held == 0);pthread_mutex_lock(&registry);held=1;}
 else {assert(held == 0 || held == 1);pthread_mutex_lock(&charger);held |= 2;}
}
static void host_unlock(void *p) {
 if (p == &sm5714_companion_lock) {assert(held == 1);held=0;pthread_mutex_unlock(&registry);}
 else {assert(held & 2);held &= ~2;pthread_mutex_unlock(&charger);}
}
'''
        code += 'typedef unsigned int u32;\n#include "'+str(ROOT/'kernel/drivers/sm5714-stage2.h')+'"\n'
        for name in ('static int sm5714_verify_switching_off_locked(',
                     'static bool sm5714_fixed_grant_locked(',
                     'int sm5714_battery_switching_acquire(',
                     'int sm5714_battery_switching_release(',
                     'int sm5714_battery_switching_check(',
                     'static void sm5714_inhibit_typec_locked(',
                     'int sm5714_battery_set_pd_contract(',
                     'int sm5714_battery_set_owned_contract(',
                     'int sm5714_battery_set_typec_charge(',
                     'void sm5714_battery_typec_fault(',
                     'static void sm5714_poll_work(',
                     'static int sm5714_suspend(', 'static int sm5714_resume(',
                     'static void sm5714_unpublish_companion(',
                     'static int sm5714_publish_companion('):
            code += function(src, name) + '\n'
        code += r'''
static struct sm5714_battery good(void) {
 return (struct sm5714_battery){.float_uv=4440000,.typec_owned=true,
 .typec_claimed=true,.typec_charge=true,.typec_mv=9000,.typec_ma=1500};
}
static void *poll(void *p) {
 for (int i=0;i<100;i++) assert(sm5714_configure_charging(p)==0);
 return NULL;
}
static void *callback(void *p) {
 (void)p;for(int i=0;i<100;i++) {
  assert(sm5714_battery_set_pd_contract(9000,1500)==0);
  assert(sm5714_battery_set_typec_charge(true)==0);
 }return NULL;
}
int main(int argc,char **argv) {
 assert(argc==3);int op=atoi(argv[1]),arg=atoi(argv[2]),r=0;
 struct sm5714_battery sm=good(),other=good();u64 lease=0,newlease=0;
 type=POWER_SUPPLY_USB_TYPE_PD;regs[0x13]=8;regs[0x15]=0x80|56;regs[0x1a]=0xc0;
 sm5714_companion=&sm;
 if(op==0) {r=sm5714_battery_switching_acquire(&lease);}
 if(op==1) {
  fail_at=arg;r=sm5714_battery_switching_acquire(&lease);
  fail_at=0;assert(sm5714_configure_charging(&sm)==0);
 }
 if(op==2) {
  drop_q4=arg==1;drop_input=arg==2;r=sm5714_battery_switching_acquire(&lease);
 }
 if(op>=3 && op<=14) {
  assert(sm5714_battery_switching_acquire(&lease)==0);io=0;
  if(op==3) r=sm5714_battery_switching_acquire(&newlease);
  if(op==4) r=sm5714_battery_switching_release(lease+1);
  if(op==5) {
   assert(sm5714_battery_set_pd_contract(9000,1500)==0);
   assert(sm5714_battery_set_typec_charge(true)==0);
   assert(sm5714_configure_charging(&sm)==0);
  }
  if(op==6) r=sm5714_battery_switching_release(lease);
  if(op==7) {
   assert(sm5714_battery_set_pd_contract(5000,500)==0);io=0;
   r=sm5714_battery_switching_release(lease);
  }
  if(op==8) {
   assert(sm5714_battery_set_typec_charge(false)==0);
   assert(sm5714_battery_set_pd_contract(9000,1500)==0);
   assert(sm5714_battery_set_typec_charge(true)==0);io=0;
   r=sm5714_battery_switching_release(lease);
  }
  if(op==9) {sm5714_battery_typec_fault();io=0;r=sm5714_battery_switching_release(lease);}
  if(op==10) {
   assert(sm5714_suspend(&sm)==0);assert(sm5714_resume(&sm)==0);
   assert(sm5714_configure_charging(&sm)==0);io=0;
   r=sm5714_battery_switching_release(lease);
  }
  if(op==11) {
   sm5714_unpublish_companion(&sm);assert(sm5714_publish_companion(&other)==0);
   assert(other.switching_inhibited);assert(sm5714_configure_charging(&other)==0);
   io=0;assert(sm5714_battery_switching_release(lease)==-ESTALE);assert(io==0);
   assert(sm5714_battery_switching_acquire(&newlease)==0);assert(newlease>lease);
   r=sm5714_battery_switching_release(newlease);assert(!sm5714_switching_blocked);
   sm5714_unpublish_companion(&other);sm.suspended=false;sm.switching_inhibited=false;
   assert(sm5714_publish_companion(&sm)==0);assert(!sm.switching_inhibited);
  }
  if(op==12) {
   mode=arg;temp_error=mode==5;
   if(mode==6)regs[0x0d]|=4;
   if(mode==8)regs[0x0e]|=128;
   r=sm5714_battery_switching_release(lease);mode=0;temp_error=0;
   assert(sm5714_configure_charging(&sm)==0);
  }
  if(op==13) {
   host_lock(&sm.chg_lock);sm5714_revoke_switching_locked(&sm);host_unlock(&sm.chg_lock);
   assert(sm5714_battery_switching_acquire(&newlease)==0);
   io=0;r=sm5714_battery_switching_release(lease);
  }
  if(op==14) {
   pthread_t a,b;assert(pthread_create(&a,NULL,poll,&sm)==0);
   assert(pthread_create(&b,NULL,callback,&sm)==0);
   pthread_join(a,NULL);pthread_join(b,NULL);
  }
 }
 if(op==15) {sm5714_switching_issuer=U64_MAX;r=sm5714_battery_switching_acquire(&lease);}
 if(op==16) {sm5714_companion=NULL;r=sm5714_battery_switching_acquire(&lease);}
 if(op==17) {
  if(arg==0)sm.suspended=true;
  if(arg==1)sm.typec_fault=true;
  if(arg==2)sm.typec_charge=false;
  if(arg==3)sm.typec_ma=99;
  if(arg==4)sm.typec_mv=10500;
  if(arg==5)sm.typec_owned=false;
  r=sm5714_battery_switching_acquire(&lease);
 }
 if(op==18) {r=sm5714_publish_companion(&other);assert(sm5714_companion==&sm);}
 if(op==19) {r=sm5714_battery_switching_acquire(NULL);}
 if(op==20) {r=sm5714_battery_switching_release(0);}
 if(op==21) {r=sm5714_configure_charging(&sm);}
 if(op==22 || op==23) {
  assert(sm5714_battery_switching_acquire(&lease)==0);sm.last_online=true;
  if(op==22)online=0;else temp_error=1;
  sm5714_poll_work((struct work_struct *)&sm.poll_work);io=0;
  r=sm5714_battery_switching_release(lease);
 }
 if(op==24) {
  assert(sm5714_battery_switching_acquire(&lease)==0);io=0;
  if(arg==1)lease++;
  if(arg==2)sm.suspended=true;
  if(arg==3)sm.typec_fault=true;
  if(arg==4)sm.typec_owned=false;
  if(arg==5)sm.typec_charge=false;
  if(arg==6)sm.switching_inhibited=false;
  if(arg==7)sm5714_companion=NULL;
  if(arg==8)lease=0;
  r=sm5714_battery_switching_check(lease);
 }

 if(op>=25&&op<=29) {
  assert(sm5714_battery_switching_acquire(&lease)==0);io=0;
  if(op==25) {
   r=sm5714_battery_set_owned_contract(lease,9000,1800,SM5714_CONTRACT_PPS);
   assert(r==0);assert(sm5714_battery_switching_check(lease)==0);
   r=sm5714_battery_switching_release(lease);
  }
  if(op==26) {
   assert(sm5714_battery_set_owned_contract(lease,8800,1800,SM5714_CONTRACT_PPS)==0);
   assert(sm5714_configure_charging(&sm)==0);assert(!(regs[0x13]&8));
   assert(sm5714_battery_set_owned_contract(lease,9000,1500,SM5714_CONTRACT_FIXED)==0);
   r=sm5714_battery_switching_release(lease);
  }
  if(op==27) {
   unsigned int mv=8800,ma=1800;enum sm5714_contract_kind kind=SM5714_CONTRACT_PPS;
   if(arg==0)mv=8180;
   if(arg==1)mv=10520;
   if(arg==2)mv=8801;
   if(arg==3)ma=1850;
   if(arg==4)ma=1799;
   if(arg==5){kind=SM5714_CONTRACT_FIXED;mv=9000;}
   if(arg==6){kind=SM5714_CONTRACT_STANDBY;ma=285;}
   if(arg==7)kind=3;
   if(arg==8){kind=SM5714_CONTRACT_FIXED;mv=ma=0;}
   if(arg==9){kind=SM5714_CONTRACT_STANDBY;mv=5000;ma=0;}
   r=sm5714_battery_set_owned_contract(lease,mv,ma,kind);
  }
  if(op==28) {
   if(arg<=6){regs[0x13]|=8;regs[0x15]=0x80|56;fail_at=arg;}
   if(arg==7)lease++;
   if(arg==8)sm.suspended=true;
   if(arg==9)sm.typec_fault=true;
   if(arg==10)sm.typec_charge=false;
   r=sm5714_battery_set_owned_contract(lease,8800,1800,SM5714_CONTRACT_PPS);
  }
  if(op==29) {
   assert(sm5714_battery_set_owned_contract(lease,8800,1800,SM5714_CONTRACT_PPS)==0);
   assert(sm5714_battery_set_owned_contract(lease,8800,284,SM5714_CONTRACT_STANDBY)==0);
   assert(sm5714_battery_switching_release(lease)==-EAGAIN);
   assert(sm.switching_lease==lease&&sm.switching_inhibited&&!(regs[0x13]&8));
   assert(sm5714_battery_set_owned_contract(lease,9000,1500,SM5714_CONTRACT_FIXED)==0);
   r=sm5714_battery_switching_release(lease);
  }
 }
 if(op==30) {
  assert(sm5714_battery_switching_acquire(&lease)==0);
  assert(sm5714_battery_set_owned_contract(lease,9000,1500,SM5714_CONTRACT_PPS)==0);
  assert(sm5714_battery_set_pd_contract(9000,1500)==0);
  io=0;r=sm5714_battery_switching_release(lease);
 }
 printf("%d %u %u %u %u %llu %llu %u %u %d %d\n",r,regs[0x13]&8,regs[0x15]&127,
 sm.switching_inhibited,sm.typec_fault,lease,sm.switching_lease,sm.typec_mv,sm.typec_ma,sm.typec_pps,io);
}
'''
        path = Path(cls.temp.name) / 'ownership.c'
        path.write_text(code)
        cls.binary = Path(cls.temp.name) / 'ownership'
        result = subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread',
                                 str(path), '-o', str(cls.binary)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    def run_case(self, op, arg=0):
        result = subprocess.run([str(self.binary), str(op), str(arg)],
                                capture_output=True, text=True, check=True, timeout=5)
        return list(map(int, result.stdout.split()))

    def test_acquire_checks_off_minimum_and_preserves_fixed_contract(self):
        r = self.run_case(0)
        self.assertEqual(r[:5], [0, 0, 0, 1, 0])
        self.assertEqual(r[5:9], [1, 1, 9000, 1500])

    def test_every_acquire_transfer_failure_keeps_inhibition_and_fault(self):
        for transfer in range(1, 7):
            with self.subTest(transfer=transfer):
                r = self.run_case(1, transfer)
                self.assertEqual(r[0], -121)
                self.assertEqual(r[1:5], [0, 0, 1, 1])
                self.assertEqual(r[6], 0)

    def test_silent_q4_and_input_write_failures_are_detected(self):
        for target in (1, 2):
            r = self.run_case(2, target)
            self.assertEqual(r[0], -5)
            self.assertEqual(r[3:5], [1, 1])

    def test_duplicate_owner_and_wrong_lease_do_no_io(self):
        for op, error in ((3, -16), (4, -116)):
            r = self.run_case(op)
            self.assertEqual((r[0], r[-1]), (error, 0))
            self.assertEqual(r[3], 1)

    def test_poll_and_same_budget_callbacks_cannot_reopen_q4(self):
        r = self.run_case(5)
        self.assertEqual(r[1:5], [0, 0, 1, 0])
        self.assertEqual(r[5], r[6])

    def test_exact_release_restores_old_fixed_ceiling(self):
        r = self.run_case(6)
        self.assertEqual(r[:5], [0, 8, 56, 0, 0])
        self.assertEqual(r[6], 0)

    def test_budget_standby_fault_and_pm_revoke_without_reenable(self):
        for op in (7, 8, 9, 10):
            with self.subTest(op=op):
                r = self.run_case(op)
                self.assertEqual((r[0], r[1], r[3], r[6], r[-1]), (-116, 0, 1, 0, 0))

    def test_rebind_preserves_inhibit_and_issuer_until_verified_release(self):
        self.assertEqual(self.run_case(11)[0], 0)

    def test_restore_failures_keep_q4_off_and_revoke(self):
        for mode in (1, 2, 3, 4, 5, 6, 8):
            r = self.run_case(12, mode)
            self.assertLess(r[0], 0)
            self.assertEqual((r[1], r[3], r[6]), (0, 1, 0))

    def test_adopt_revoked_inhibit_cannot_reuse_old_lease(self):
        r = self.run_case(13)
        self.assertEqual((r[0], r[-1]), (-116, 0))
        self.assertGreater(r[6], r[5])

    def test_threaded_poller_and_companion_obey_lock_order_and_inhibit(self):
        r = self.run_case(14)
        self.assertEqual(r[1:5], [0, 0, 1, 0])

    def test_issuer_exhaustion_never_wraps_or_touches_hardware(self):
        r = self.run_case(15)
        self.assertEqual((r[0], r[5], r[-1]), (-75, 0, 0))

    def test_absence_and_invalid_grants_are_refused_without_io(self):
        self.assertEqual(self.run_case(16)[0], -19)
        for arg in range(6):
            r = self.run_case(17, arg)
            self.assertEqual((r[0], r[5], r[-1]), (-11, 0, 0))

    def test_duplicate_publish_and_bad_arguments_do_not_replace_companion(self):
        for op, error in ((18, -16), (19, -22), (20, -22)):
            r = self.run_case(op)
            self.assertEqual((r[0], r[-1]), (error, 0))

    def test_actual_poller_detach_and_sensor_fault_revoke_lease(self):
        for op in (22, 23):
            r = self.run_case(op)
            self.assertEqual((r[0], r[1], r[3], r[6], r[-1]), (-116, 0, 1, 0, 0))

    def test_default_fixed_path_stays_enabled_at_original_current(self):
        r = self.run_case(21)
        self.assertEqual(r[:5], [0, 8, 56, 0, 0])

    def test_read_only_lease_check_has_no_hardware_side_effects(self):
        for arg,error in ((0,0),(1,-116),(2,-11),(3,-11),(4,-11),(5,-11),(6,-116),(7,-19),(8,-22)):
            with self.subTest(arg=arg):
                r=self.run_case(24,arg)
                self.assertEqual((r[0],r[-1]),(error,0))
                self.assertEqual(r[1],0)
                self.assertEqual(r[6],1)

    def test_owned_9v_pps_cannot_be_released_as_fixed_9v(self):
        r=self.run_case(25)
        self.assertEqual((r[0],r[1],r[2],r[3],r[6],r[9]),(-11,0,0,1,1,1))
        self.assertEqual(r[7:9],[9000,1800])

    def test_owned_pps_budget_keeps_off_then_fixed_restore_can_release(self):
        r=self.run_case(26)
        self.assertEqual(r[:5],[0,8,56,0,0])
        self.assertEqual(r[6:10],[0,9000,1500,0])

    def test_owned_invalid_bounds_encoding_and_kind_inhibit_and_revoke(self):
        for arg in range(10):
            with self.subTest(arg=arg):
                r=self.run_case(27,arg)
                self.assertEqual((r[0],r[1],r[2],r[3],r[4],r[6]),(-34,0,0,1,1,0))

    def test_every_owned_off_transfer_failure_faults_without_grant(self):
        for transfer in range(1,7):
            r=self.run_case(28,transfer)
            self.assertEqual((r[0],r[1],r[3],r[4],r[6]),(-121,0,1,1,0))

    def test_stale_pm_fault_and_charge_off_owned_callback_does_no_io(self):
        for arg,error in ((7,-116),(8,-11),(9,-11),(10,-11)):
            r=self.run_case(28,arg)
            self.assertEqual((r[0],r[-1]),(error,0))
            self.assertEqual(r[1],0)

    def test_off_only_fixed_return_standby_preserves_lease_but_refuses_release(self):
        self.assertEqual(self.run_case(29)[:5],[0,8,56,0,0])

    def test_ordinary_same_numbers_pps_to_fixed_change_revokes_lease(self):
        r=self.run_case(30)
        self.assertEqual((r[0],r[1],r[3],r[6],r[9],r[-1]),(-116,0,1,0,0,0))


if __name__ == '__main__':
    unittest.main()
