# Live evidence monitor for the GTS9 bring-up USB gadget (Windows host side).
#
# Presence of the gadget proves the initramfs script ran (PID 1 reached
# userspace); serial output proves /dev/kmsg streaming works.  The tablet's USB
# port is the only channel that can carry a live log, so this runs on the
# Windows side of the WSL host while the tablet boots.
#
#	# from WSL, with the tablet currently in recovery:
#	powershell.exe -NoProfile -ExecutionPolicy Bypass \
#	  -File "\\\\wsl.localhost\\<distro>\\<repo>\\scripts\\usb-monitor.ps1" \
#	  -Out "D:\\android\\gts9-usb-monitor.log" -Minutes 25
#
# The wait for VID_18D1 (recovery's own adb interface) to disappear comes first,
# so the gadget can never be confused with TWRP's adb.
param(
    [string]$Out = "$env:TEMP\gts9-usb-monitor.log",
    [int]$Minutes = 25
)

function Log([string]$msg) {
    $line = "{0} {1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"), $msg
    Add-Content -Path $Out -Value $line
    Write-Output $line
}

Log "monitor start: waiting for the tablet to leave recovery, then for VID_0525&PID_A4A7"

# Recovery enumerates as Google adb (18d1:d001); wait for it to go away first so
# the gadget cannot be confused with it.
$deadline = (Get-Date).AddMinutes($Minutes)
while ((Get-Date) -lt $deadline) {
    $adb = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -like '*VID_18D1*' }
    if (-not $adb) { Log "recovery USB interface gone; watching for the gadget"; break }
    Start-Sleep -Seconds 2
}
$deadline = (Get-Date).AddMinutes($Minutes)
$found = $false
while ((Get-Date) -lt $deadline) {
    $dev = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -like '*VID_0525*PID_A4A7*' }
    if ($dev) {
        Log ("GADGET PRESENT: " + ($dev.InstanceId -join ','))
        $found = $true
        break
    }
    Start-Sleep -Seconds 2
}

if (-not $found) {
    Log "NO GADGET after $Minutes minutes (initramfs did not reach userspace, or the gadget could not bind)"
    exit 2
}

# Give Windows a moment to enumerate the CDC-ACM interface, then read it.
Start-Sleep -Seconds 5
$ports = [System.IO.Ports.SerialPort]::GetPortNames()
Log ("COM ports: " + ($ports -join ','))
if (-not $ports) {
    Log "gadget present but no COM port yet; waiting 30 s"
    Start-Sleep -Seconds 30
    $ports = [System.IO.Ports.SerialPort]::GetPortNames()
    Log ("COM ports: " + ($ports -join ','))
}
if (-not $ports) {
    Log "NO COM PORT: gadget bound but the ACM interface did not enumerate"
    exit 3
}

$port = $ports[-1]
Log "opening $port at 115200 and logging for 180 s"
try {
    $sp = New-Object System.IO.Ports.SerialPort $port, 115200, 'None', 8, 'One'
    $sp.ReadTimeout = 5000
    $sp.NewLine = "`n"
    $sp.Open()
    Log "port open"
    $end = (Get-Date).AddSeconds(180)
    while ((Get-Date) -lt $end) {
        try {
            $line = $sp.ReadLine()
            if ($line) { Add-Content -Path $Out -Value ("SERIAL " + $line.TrimEnd()) }
        } catch [TimeoutException] {
            # no data for a while; keep waiting until the deadline
        }
    }
    $sp.Close()
    Log "port closed"
} catch {
    Log ("serial error: " + $_.Exception.Message)
    exit 4
}
Log "monitor done"
