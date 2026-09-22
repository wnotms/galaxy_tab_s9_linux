# Host-side helper for the SM-X710 bring-up console (Windows PowerShell).
#
# The tablet's gadget exposes a CDC-ACM console and the microSD card read-only
# on the same USB port, so a boot can be driven and its log collected without
# TWRP and without touching the tablet:
#
#   powershell -File scripts/console-session.ps1 -Port COM17 \
#       -Commands 'uname -a','df -h','dmesg | tail -5'
#   powershell -File scripts/collect-card.ps1 -Drive G: -Dest D:\gts9-card
#
# console-session.ps1 opens the port at 115200 8N1, sends each command and logs
# everything the tablet answers; typing gts9-to-recovery there writes the BCB
# and reboots the tablet into TWRP.  serial-link-test.ps1 is the marker-based
# link check used in test 030, and collect-card.ps1 copies the report and its
# sha256 sidecar off the exported volume.
#
param(
    [string]$Port = "COM17",
    [string]$Out = "$env:TEMP\gts9-console.log",
    [string[]]$Commands = @("uname -a", "uptime", "ls /dev/mmcblk* /dev/sd* | head"),
    [string]$Then = "",
    [int]$Seconds = 30
)
function Log([string]$m) {
    $l = "{0} {1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"), $m
    Add-Content -Path $Out -Value $l; Write-Output $l
}
$sp = $null
$openDeadline = (Get-Date).AddSeconds(240)
while ((Get-Date) -lt $openDeadline) {
    try {
        $sp = New-Object System.IO.Ports.SerialPort $Port, 115200, 'None', 8, 'One'
        $sp.ReadTimeout = 3000; $sp.WriteTimeout = 8000
        $sp.DtrEnable = $true; $sp.RtsEnable = $true; $sp.NewLine = "`n"
        $sp.Open(); Log "console open on $Port"; break
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $sp -or -not $sp.IsOpen) { Log "could not open $Port"; exit 1 }
$sp.DiscardInBuffer()
Start-Sleep -Seconds 3   # let the shell on the tablet come up after the open
foreach ($cmd in $Commands) {
    $got = 0
    foreach ($attempt in 1..2) {
        try { $sp.WriteLine($cmd); Log ("SENT  " + $cmd) } catch { Log ("send failed: " + $_.Exception.Message); break }
        $until = (Get-Date).AddSeconds(8)
        while ((Get-Date) -lt $until) {
            try { $line = $sp.ReadLine(); if ($line) { Log ("RECV  " + $line.TrimEnd()); $got++ } } catch [TimeoutException] { }
        }
        if ($got -gt 0) { break }
        Log "no output for '$cmd'; retrying once"
        Start-Sleep -Seconds 2
    }
}
if ($Then -ne "") {
    Start-Sleep -Seconds 2
    try { $sp.WriteLine($Then); Log ("SENT  " + $Then) } catch { Log ("send failed: " + $_.Exception.Message) }
    $until = (Get-Date).AddSeconds(5)
    while ((Get-Date) -lt $until) { try { $line = $sp.ReadLine(); if ($line) { Log ("RECV  " + $line.TrimEnd()) } } catch [TimeoutException] { } }
}
try { $sp.Close() } catch { }
Log "console session done"
