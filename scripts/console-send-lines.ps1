# Send a local text file to the tablet's console as input lines.
#
# Used to move small artefacts (a base64-encoded helper binary, a shell script)
# onto the tablet without a recovery/TWRP leg.  Pre-commands are sent and read
# one at a time; the file body is then streamed without waiting, because a
# heredoc consumer is the thing that must keep up.  Post-commands are read
# again, and the caller is expected to verify a checksum.
#
#   powershell -ExecutionPolicy Bypass -File scripts/console-send-lines.ps1 `
#       -File C:\gts9-work\pk.b64 -Out C:\gts9-work\send.log `
#       -Pre "stty -echo; rm -f /tmp/pk.b64; cat > /tmp/pk.b64 <<'GTS9EOF'" `
#       -Post 'GTS9EOF','stty echo','sha256sum /tmp/pk.b64'
param(
    [string]$Port = "COM17",
    [string]$File = "",
    [string]$PreFile = "",
    [string]$PostFile = "",
    [string]$Out = "$env:TEMP\gts9-send-lines.log",
    [string[]]$Pre = @(),
    [string[]]$Post = @(),
    [int]$WaitReadySeconds = 30,
    [int]$InterLineMs = 8,
    [int]$ReadSeconds = 6
)

$ErrorActionPreference = 'Continue'

# Command lists come from files so that a caller can pass them without relying
# on PowerShell -File array binding (which delivers "a,b,c" as one string).
$preCommands = @()
if ($PreFile -ne "") { $preCommands += @(Get-Content -LiteralPath $PreFile | Where-Object { $_ -ne "" }) }
$preCommands += @($Pre | Where-Object { $_ -ne "" })
$postCommands = @()
if ($PostFile -ne "") { $postCommands += @(Get-Content -LiteralPath $PostFile | Where-Object { $_ -ne "" }) }
$postCommands += @($Post | Where-Object { $_ -ne "" })

function Log([string]$m) {
    $l = "{0} {1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ"), $m
    try { Add-Content -Path $Out -Value $l } catch { }
    Write-Output $l
}

$sp = New-Object System.IO.Ports.SerialPort $Port, 115200, 'None', 8, 'One'
$sp.ReadTimeout = 400; $sp.WriteTimeout = 4000
$sp.DtrEnable = $true; $sp.RtsEnable = $true; $sp.NewLine = "`n"
try { $sp.Open() } catch { Log ("could not open ${Port}: " + $_.Exception.Message); exit 1 }
Log "port open on $Port"

function ReadFor([int]$seconds) {
    $got = @()
    $until = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $until) {
        try { $line = $sp.ReadLine(); if ($line) { $got += $line.TrimEnd() } } catch [TimeoutException] { }
    }
    return $got
}

if ($WaitReadySeconds -gt 0) {
    try { $sp.DiscardInBuffer() } catch { }
    $ready = $false
    $deadline = (Get-Date).AddSeconds($WaitReadySeconds)
    $n = 0
    while ((Get-Date) -lt $deadline -and -not $ready) {
        $n++
        $marker = "SENDREADY$n"
        try { $sp.WriteLine("echo $marker") } catch { }
        foreach ($line in (ReadFor 1)) { if ($line -match $marker) { $ready = $true } }
    }
    Log "shell ready=$ready"
}

foreach ($cmd in $preCommands) {
    try { $sp.WriteLine($cmd); Log ("SENT  " + $cmd) } catch { Log ("send failed: " + $_.Exception.Message) }
    foreach ($line in (ReadFor $ReadSeconds)) { Log ("RECV  " + $line) }
}

if ($File -ne "") {
    $body = Get-Content -LiteralPath $File
    Log ("streaming {0} line(s) from {1}" -f $body.Count, $File)
    foreach ($line in $body) {
        try { $sp.WriteLine($line) } catch { Log ("send failed: " + $_.Exception.Message); break }
        if ($InterLineMs -gt 0) { Start-Sleep -Milliseconds $InterLineMs }
    }
    Log "body sent"
}

foreach ($cmd in $postCommands) {
    try { $sp.WriteLine($cmd); Log ("SENT  " + $cmd) } catch { Log ("send failed: " + $_.Exception.Message) }
    foreach ($line in (ReadFor $ReadSeconds)) { Log ("RECV  " + $line) }
}

try { $sp.Close() } catch { }
Log "send done"
