# Fast console helper: open the port, wait for the tablet's shell to answer, then
# run the commands.  The point is to stop paying fixed sleeps: console-session.ps1
# sleeps 3 s before every session and waits 8 s per command, which is fine for a
# settled shell but wastes a minute per test when the only question is "is the
# shell up yet?".  This one sends a heartbeat every PollMs and returns as soon as
# the shell echoes it, so a boot costs its real duration and nothing more.
#
#   powershell -ExecutionPolicy Bypass -File scripts/console-run.ps1 `
#       -Out D:\android\gts9-testNNN\boot.log -Commands 'dmesg | grep -a pogo'
#
# -WaitReadySeconds 0 skips the heartbeat and runs the commands immediately.
param(
    [string]$Port = "COM17",
    [string]$Out = "$env:TEMP\gts9-console-run.log",
    [string[]]$Commands = @("uname -a"),
    [int]$WaitReadySeconds = 120,
    [int]$PollMs = 1000,
    [int]$ReadSeconds = 4,
    # Nominal only on this console: COM17/COM19 are USB CDC-ACM gadget ports, so
    # the host's line coding is not what clocks the data - the USB bulk pipe is.
    # Exposed as a parameter so that claim can be measured rather than believed.
    [int]$Baud = 115200
)
function Log([string]$m) {
    $l = "{0} {1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"), $m
    try { Add-Content -Path $Out -Value $l } catch { }
    Write-Output $l
}
$sp = $null
$openDeadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $openDeadline) {
    try {
        $sp = New-Object System.IO.Ports.SerialPort $Port, $Baud, 'None', 8, 'One'
        $sp.ReadTimeout = 700; $sp.WriteTimeout = 4000
        $sp.DtrEnable = $true; $sp.RtsEnable = $true; $sp.NewLine = "`n"
        $sp.Open(); Log "console open on $Port"; break
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $sp -or -not $sp.IsOpen) { Log "could not open $Port"; exit 1 }

# When the tablet resets, the port closes and every ReadLine() then throws.  Only
# TimeoutException used to be caught, so each iteration wrote a full PowerShell
# error record and the capture became mostly stack traces: test-184's
# probe-A-5-raw.txt is 24 608 lines of them, and this round's shutdown-N-trigger.txt
# files reached ~2 MB each.  The failure is worth recording - it is the moment the
# device disappeared - but once.  Reading continues so a port that comes back still
# produces output, and the message is re-armed by the next line that arrives.
$script:readErrorLogged = $false
function ReadFor([int]$seconds) {
    $got = @()
    $until = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $until) {
        try {
            $line = $sp.ReadLine()
            if ($line) { $got += $line.TrimEnd(); $script:readErrorLogged = $false }
        } catch [TimeoutException] {
            # Normal: no complete line arrived within ReadTimeout.
        } catch {
            if (-not $script:readErrorLogged) {
                Log ("read failed: " + $_.Exception.Message + " (further read errors suppressed until a line arrives)")
                $script:readErrorLogged = $true
            }
            Start-Sleep -Milliseconds 100
        }
    }
    return $got
}
function Drain() { [void](ReadFor 1) }

$ready = $false
if ($WaitReadySeconds -gt 0) {
    try { $sp.DiscardInBuffer() } catch { }
    $deadline = (Get-Date).AddSeconds($WaitReadySeconds)
    $n = 0
    while ((Get-Date) -lt $deadline) {
        $n++
        $marker = "READY$n"
        try { $sp.WriteLine("echo $marker") } catch { }
        foreach ($line in (ReadFor ([Math]::Max(1, [int]($PollMs / 1000))))) {
            Log ("RECV  " + $line)
            if ($line -match $marker) { $ready = $true }
        }
        if ($ready) { Log "shell answered after $n poll(s)"; break }
    }
    if (-not $ready) { Log "shell never answered within $WaitReadySeconds s" }
}
foreach ($cmd in $Commands) {
    if ($cmd -eq '') {
        # Pure listen: do not write at all.  A write can block (and time out) when the
        # other side deasserts flow control, and then the capture never happens - which
        # is exactly what hid the state of the Debian serial line.
        Log 'listening only (no command sent)'
        foreach ($line in (ReadFor $ReadSeconds)) { Log ("RECV  " + $line) }
        continue
    }
    try { $sp.WriteLine($cmd); Log ("SENT  " + $cmd) } catch { Log ("send failed: " + $_.Exception.Message) }
    foreach ($line in (ReadFor $ReadSeconds)) { Log ("RECV  " + $line) }
}
try { $sp.Close() } catch { }
Log "console run done (ready=$ready)"
