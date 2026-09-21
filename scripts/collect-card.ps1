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
function Log([string]$m) { $l = "{0} {1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"), $m; Add-Content -Path $Out -Value $l; Write-Output $l }
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$deadline = (Get-Date).AddSeconds(300)
while ((Get-Date) -lt $deadline) {
    if (Test-Path "$Drive\gts9-bringup-report.txt") {
        Copy-Item "$Drive\gts9-bringup-report.txt" "$Dest\bringup-report.txt" -Force
        if (Test-Path "$Drive\gts9-bringup-report.txt.sha256") { Copy-Item "$Drive\gts9-bringup-report.txt.sha256" "$Dest\bringup-report.txt.sha256" -Force }
        if (Test-Path "$Drive\gts9-serial-in.txt") { Copy-Item "$Drive\gts9-serial-in.txt" "$Dest\serial-in.txt" -Force }
        Log ("collected from $Drive : " + ((Get-ChildItem $Dest | ForEach-Object { $_.Name + '(' + $_.Length + ')' }) -join ', '))
        exit 0
    }
    Start-Sleep -Seconds 5
}
Log "no report appeared on $Drive within the window"
exit 1
