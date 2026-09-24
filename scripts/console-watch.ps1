# Continuous console + USB-presence watcher for the X710.
#
# console-run.ps1 is built for "run these commands and return"; a shutdown test
# needs the opposite: keep reading for the whole window, timestamp every line,
# notice exactly when the USB gadget disappears, and keep trying to reopen the
# port so an automatic restart (VBUS insertion boots the tablet) is captured
# too.  The observer stays on the host, so it works when the tablet's own USB
# device node is gone.
#
#   powershell -ExecutionPolicy Bypass -File scripts/console-watch.ps1 `
#       -Out C:\gts9-work\p4-poweroff.log -Seconds 900 `
#       -Command 'sudo poweroff' -CommandAtSeconds 15
#
# -Command '' means listen only.  Presence is sampled twice: the COM port list
# (cheap, catches the gadget going away) and the PnP instance (catches the
# tablet disappearing from the bus even if another driver keeps the port name).
param(
    [string]$Port = "COM17",
    [string]$Out = "$env:TEMP\gts9-console-watch.log",
    [int]$Seconds = 900,
    [string]$Command = "",
    [int]$CommandAtSeconds = 10,
    [int]$PollMs = 500,
    [string]$UsbInstanceLike = "USB\VID_0525&PID_A4A7*"
)

$ErrorActionPreference = 'Continue'
$start = (Get-Date).ToUniversalTime()

function Log([string]$m) {
    $l = "{0} {1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ"), $m
    try { Add-Content -Path $Out -Value $l } catch { }
    Write-Output $l
}

function ComPorts() {
    try { return @([System.IO.Ports.SerialPort]::GetPortNames()) } catch { return @() }
}

function UsbPresent() {
    try {
        $d = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
             Where-Object { $_.InstanceId -like $UsbInstanceLike }
        return [bool]$d
    } catch { return $false }
}

Log "watch start: port=$Port seconds=$Seconds command='$Command' at ${CommandAtSeconds}s"

$sp = $null
$sent = $false
$lastCom = $null
$lastUsb = $null
$disconnects = 0
$reconnects = 0
$lines = 0
$deadline = $start.AddSeconds($Seconds)
$nextPresence = $start

function ClosePort([string]$why) {
    if ($script:sp) {
        try { $script:sp.Close() } catch { }
        $script:sp = $null
        Log "port closed ($why)"
    }
}

function TryOpen() {
    try {
        $p = New-Object System.IO.Ports.SerialPort $Port, 115200, 'None', 8, 'One'
        $p.ReadTimeout = 300; $p.WriteTimeout = 2000
        $p.DtrEnable = $true; $p.RtsEnable = $true; $p.NewLine = "`n"
        $p.Open()
        return $p
    } catch { return $null }
}

while ((Get-Date).ToUniversalTime() -lt $deadline) {
    $now = (Get-Date).ToUniversalTime()

    # ---- presence sampling (once a second at most) ----
    if ($now -ge $nextPresence) {
        $nextPresence = $now.AddSeconds(1)
        $coms = @(ComPorts)
        $hasCom = $coms -contains $Port
        $hasUsb = UsbPresent
        if ($hasCom -ne $lastCom) {
            Log ("PRESENCE com={0} ports=[{1}]" -f $hasCom, ($coms -join ','))
            $lastCom = $hasCom
            if (-not $hasCom) { $disconnects++ } elseif ($disconnects -gt 0) { $reconnects++ }
        }
        if ($hasUsb -ne $lastUsb) {
            Log ("PRESENCE usb0525:a4a7={0}" -f $hasUsb)
            $lastUsb = $hasUsb
        }
    }

    # ---- serial ----
    if (-not $sp) {
        $sp = TryOpen
        if ($sp) {
            Log "port open on $Port"
            try { $sp.DiscardInBuffer() } catch { }
            # A fresh port means a fresh boot: re-arm the command so a single
            # watcher can drive a test across an automatic restart.
            if ($Command -ne '' -and -not $sent -and `
                ((Get-Date).ToUniversalTime() - $start).TotalSeconds -ge $CommandAtSeconds) {
                $sent = $true
            }
        } else {
            Start-Sleep -Milliseconds 500
            continue
        }
    }

    try {
        $line = $sp.ReadLine()
        if ($line) { Log ("RECV  " + $line.TrimEnd()); $lines++ }
    } catch [TimeoutException] {
    } catch {
        Log ("read failed: " + $_.Exception.Message)
        ClosePort "read error"
    }

    if ($Command -ne '' -and -not $sent -and `
        ((Get-Date).ToUniversalTime() - $start).TotalSeconds -ge $CommandAtSeconds) {
        try {
            $sp.WriteLine($Command)
            $sent = $true
            Log ("SENT  " + $Command)
        } catch {
            Log ("send failed: " + $_.Exception.Message)
            ClosePort "write error"
        }
    }
}

ClosePort "watch end"
Log ("watch done: lines=$lines com_disconnects=$disconnects com_reconnects=$reconnects")
