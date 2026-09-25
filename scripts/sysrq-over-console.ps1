# Send a serial BREAK followed by a SysRq command to a kernel console, and keep
# whatever the kernel prints.  Exists for one situation: a boot whose kernel is
# still answering (ICMP, TCP RST) while its userspace is gone, so no shell, no
# ssh and no dmesg are available - and the only way to learn what is stuck is to
# ask the kernel over the console it is still writing to.
#
#   -Port COM19 -SysRq l -ReadSeconds 20
#
# The sequence is the classic one the kernel's serial console expects: BREAK,
# then the command character within a few seconds.  CONFIG_MAGIC_SYSRQ_SERIAL=y
# is set in this kernel and CONFIG_MAGIC_SYSRQ_SERIAL_SEQUENCE is empty, which is
# the "use a BREAK" case.
#
# Nothing here is a reboot unless the SysRq command is one.  Callers pass 'l'
# (backtrace every CPU), 'w' (blocked tasks) or 't' (all tasks); 'b' reboots.
param(
    [string]$Port = "COM19",
    [int]$Baud = 115200,
    [string]$SysRq = "l",
    [int]$ReadSeconds = 20,
    [string]$Out = "C:\Users\ms\AppData\Local\Temp\gts9-sysrq.log"
)

$ErrorActionPreference = "Continue"
$log = New-Object System.Collections.Generic.List[string]

function Log([string]$m) {
    $line = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ") + " " + $m
    $log.Add($line)
    $line | Tee-Object -FilePath $Out -Append
}

$sp = New-Object System.IO.Ports.SerialPort $Port, $Baud, "None", 8, "One"
$sp.ReadTimeout = 1000
$sp.NewLine = "`n"
try {
    $sp.Open()
} catch {
    Log ("could not open " + $Port + ": " + $_.Exception.Message)
    exit 1
}
Log ("port open on " + $Port + " at " + $Baud)

try {
    Log "sending BREAK"
    $sp.BreakState = $true
    Start-Sleep -Milliseconds 400
    $sp.BreakState = $false
    Start-Sleep -Milliseconds 150

    Log ("sending SysRq '" + $SysRq + "'")
    $sp.Write($SysRq)

    $deadline = (Get-Date).AddSeconds($ReadSeconds)
    $got = 0
    while ((Get-Date) -lt $deadline) {
        try {
            $chunk = $sp.ReadExisting()
        } catch {
            $chunk = ""
        }
        if ($chunk -and $chunk.Length -gt 0) {
            $got += $chunk.Length
            foreach ($l in ($chunk -split "`r?`n")) {
                if ($l.Trim().Length -gt 0) { Log ("RECV  " + $l) }
            }
        } else {
            Start-Sleep -Milliseconds 200
        }
    }
    Log ("bytes received: " + $got)
} finally {
    try { $sp.Close() } catch { }
    Log "console run done"
}
