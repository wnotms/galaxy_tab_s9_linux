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
    [string]$Port = "COM17",
    [string]$Out = "$env:TEMP\gts9-serial-test.log",
    [string]$Send = "PING-GTS9-030",
    [int]$Seconds = 90
)
function Log([string]$m) {
    $l = "{0} {1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"), $m
    Add-Content -Path $Out -Value $l; Write-Output $l
}
Log "serial test on $Port, will send '$Send'"
$sp = $null
$openDeadline = (Get-Date).AddSeconds(180)
$attempt = 0
while ((Get-Date) -lt $openDeadline) {
    $attempt++
    try {
        $sp = New-Object System.IO.Ports.SerialPort $Port, 115200, 'None', 8, 'One'
        $sp.ReadTimeout = 2000
        $sp.WriteTimeout = 8000
        $sp.DtrEnable = $true
        $sp.RtsEnable = $true
        $sp.NewLine = "`n"
        $sp.Open()
        Log ("port open (attempt $attempt)")
        break
    } catch {
        if ($attempt % 5 -eq 1) { Log ("open attempt $attempt failed: " + $_.Exception.Message) }
        Start-Sleep -Seconds 3
    }
}
if (-not $sp -or -not $sp.IsOpen) { Log "never managed to open $Port"; exit 1 }
$deadline = (Get-Date).AddSeconds($Seconds)
$read = 0
while ((Get-Date) -lt $deadline -and $read -eq 0) {
    try {
        $line = $sp.ReadLine()
        if ($line) { $read++; Log ("READ  " + $line.TrimEnd()) }
    } catch [TimeoutException] { }
}
if ($read -eq 0) { Log "NOTHING RECEIVED in the read window" }
$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $sp.WriteLine($Send)
    $sw.Stop()
    Log ("WRITE ok after " + $sw.ElapsedMilliseconds + " ms: " + $Send)
} catch {
    $sw.Stop()
    Log ("WRITE failed after " + $sw.ElapsedMilliseconds + " ms: " + $_.Exception.Message)
}
$tail = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $tail) {
    try {
        $line = $sp.ReadLine()
        if ($line) { Log ("READ  " + $line.TrimEnd()) }
    } catch [TimeoutException] { }
    catch { Log ("read error: " + $_.Exception.Message); break }
}
try { $sp.Close() } catch { }
Log "serial test done"
