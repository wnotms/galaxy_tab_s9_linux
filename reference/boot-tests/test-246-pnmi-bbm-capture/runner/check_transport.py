import control,subprocess,base64,json,datetime,sys
phase=sys.argv[1] if len(sys.argv)>1 else "production"
s,_=control.shell(phase,'transport-services','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; systemctl is-active ssh gts9-usb-acm gts9-usb-adb-hold gts9-adbd; ip -br addr; cat /sys/module/ramoops/parameters/ecc',timeout=10);print(s)
script='''$ErrorActionPreference = "Stop"
$c = [System.Net.Sockets.TcpClient]::new()
try {
  $a = $c.BeginConnect("169.254.42.1", 22, $null, $null)
  if (-not $a.AsyncWaitHandle.WaitOne(5000)) { throw "SSH connect timeout" }
  $c.EndConnect($a)
  $s = $c.GetStream(); $s.ReadTimeout = 5000
  $b = New-Object byte[] 512
  $n = $s.Read($b, 0, $b.Length)
  $text = [Text.Encoding]::ASCII.GetString($b, 0, $n)
  if (-not $text.StartsWith("SSH-2.0-")) { throw "No SSH banner" }
  Write-Output $text.Trim()
} finally { $c.Dispose() }
'''
cmd=['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()]
r=subprocess.run(cmd,capture_output=True,timeout=15);p=control.P/phase
(p/'ssh-banner.txt').write_bytes(r.stdout);(p/'ssh-banner.stderr').write_bytes(r.stderr)
(p/'ssh-banner.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'transport':'Windows TCP over existing USB NCM','target':'169.254.42.1:22','status':r.returncode,'authenticated_shell_tested':False,'configuration_changed':False},indent=2)+'\n')
print(r.returncode,r.stdout.decode(errors='replace'),r.stderr.decode(errors='replace'));assert r.returncode==0
