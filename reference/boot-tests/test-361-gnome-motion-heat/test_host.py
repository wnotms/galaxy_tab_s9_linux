from pathlib import Path
import importlib.util,unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('heat',ROOT/'userspace/gnome/thermal.py')
heat=importlib.util.module_from_spec(spec);spec.loader.exec_module(heat)
class HeatCounters(unittest.TestCase):
 def test_actual_proc_stat_parser(self):
  text=Path('/proc/self/stat').read_text();fields=text[text.rindex(')')+2:].split()
  self.assertEqual(heat.process_stat(text),{'start_ticks':int(fields[19]),'cpu_ticks':int(fields[11])+int(fields[12])})
 def test_parenthesized_process_name(self):
  fields=['S']+['0']*19;fields[11]='15';fields[12]='8';fields[19]='123'
  self.assertEqual(heat.process_stat('1 (name with ) parentheses) '+' '.join(fields)),{'start_ticks':123,'cpu_ticks':23})
 def test_guest_not_double_counted_and_iowait_separate(self):
  self.assertEqual(heat.cpu_activity([0]*10,[20,0,10,60,10,0,0,0,20,0]),30)
 def test_counter_reset_rejected(self):
  with self.assertRaises(ValueError):heat.cpu_activity([10]*8,[0]*8)
 def test_pid_reuse_and_exited_process_not_attributed(self):
  old={'1':{'start_ticks':1,'cpu_ticks':20},'2':{'start_ticks':1,'cpu_ticks':500}}
  new={'1':{'start_ticks':2,'cpu_ticks':100,'comm':'new'}}
  self.assertEqual(heat.process_activity(old,new,10,100),[])
 def test_multithreaded_cpu_can_exceed_one_cpu(self):
  before={'1':{'start_ticks':1,'cpu_ticks':0}}
  after={'1':{'start_ticks':1,'cpu_ticks':2500,'comm':'app'}}
  self.assertEqual(heat.process_activity(before,after,10,100)[0]['one_cpu_percent'],250)
 def test_pack_threshold_is_decicelsius_and_fail_closed(self):
  self.assertTrue(heat.safe_pack({'health':'Good','temp':'419'}))
  self.assertFalse(heat.safe_pack({'health':'Good','temp':'420'}))
  self.assertFalse(heat.safe_pack({'health':'Unknown','temp':'250'}))
  with self.assertRaises(ValueError):heat.safe_pack({'health':'Good','temp':'invalid'})
 def test_boot_change_interval_rejected(self):
  with self.assertRaises(ValueError):heat.interval({'boot_id':'a'},{'boot_id':'b'})
if __name__=='__main__':unittest.main()
