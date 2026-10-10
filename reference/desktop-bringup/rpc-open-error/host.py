import unittest, json, time, pathlib, io, sys
R=pathlib.Path.cwd(); sys.path.insert(0,str(R/'tests')); start=time.monotonic()
modules=['test_rpc_open_error_profile','test_rpc_stat_profile','test_ssc_rpc_wire','test_rpc_return_profile','test_libssc_wait_profile']
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in modules)
def flatten(t):
 for x in t:
  if isinstance(x,unittest.TestSuite): yield from flatten(x)
  else: yield x.id()
ids=list(flatten(suite)); stream=io.StringIO(); result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
E=R/'reference/desktop-bringup/rpc-open-error'; (E/'host-tests.txt').write_text(stream.getvalue())
report=dict(executed=True,selected=ids,tests_run=result.testsRun,successful=result.wasSuccessful(),skipped=result.skipped,failures=result.failures,errors=result.errors,seconds=time.monotonic()-start,full_regression=dict(executed=False,reason='Owner requested direct affected tests; no test routing/kernel/default-source changes.'),kernel_build=dict(executed=False,reason='Userspace-only callback/status profile; kernel unchanged.'),github_actions=False)
(E/'HOST_TESTS.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps({k:report[k] for k in ['tests_run','successful','skipped','seconds']})); sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
