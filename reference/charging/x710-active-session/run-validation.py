#!/usr/bin/env python3
"""Affected-only real-C regression; no device operations."""
import gzip,json,subprocess,time,unittest,sys
from pathlib import Path
R=Path(__file__).resolve().parents[3];D=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'tests'))
modules=['test_x710_charge_controller','test_sm5440_native_control','test_sm5440_actuator','test_sm5440_conversion','test_sm5440_supervisor','test_sm5440_watchdog','test_x710_charge_observer','test_x710_charging_policy','test_x710_pd_session','test_x710_direct_transaction','test_sm5714_stage2_pd','test_sm5714_pack_snapshot','test_sm5714_owned_observer','test_sm5714_runtime_snapshot','test_container_kernel_config']
suite=unittest.defaultTestLoader.loadTestsFromNames(modules)
start=time.monotonic()
with (D/'tests.log.tmp').open('w') as f:
 result=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
report={'executed':True,'modules':modules,'tests_run':result.testsRun,'seconds':time.monotonic()-start,'failures':[t.id() for t,_ in result.failures],'errors':[t.id() for t,_ in result.errors],'skips':[t.id() for t,_ in result.skipped],'valid':result.wasSuccessful() and not result.skipped,'full_executed':False,'reason':'Actual controller + native executor/policy/TCPM/observer/pack/container dependencies; no suite routing changed.'}
(D/'tests.json').write_text(json.dumps(report,indent=2)+'\n')
p=D/'tests.log.tmp';(D/'tests.log.gz').write_bytes(gzip.compress(p.read_bytes(),mtime=0));p.unlink()
print(json.dumps(report));sys.exit(0 if report['valid'] else 1)
