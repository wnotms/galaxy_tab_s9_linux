#!/usr/bin/env bash
# Read-only connected-device capture. Run before any TWRP transition or write.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../../../.." && pwd)
capture_dir="$repo_root/reference/boot-tests/test-255-sm5714-fixed-pd/attempt-01/preflight"
adb=/mnt/d/android/platform-tools/adb.exe
wifi_addr=${GTS9_TEST255_WIFI:-10.191.121.241}
ssh_tool="$repo_root/scripts/gts9-ssh.sh"
powershell=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe

mkdir -p "$capture_dir"

capture() {
    local name=$1
    shift
    printf '%q ' "$@" > "$capture_dir/$name.command.txt"
    printf '\n' >> "$capture_dir/$name.command.txt"
    if "$@" > "$capture_dir/$name.txt" 2> "$capture_dir/$name.stderr"; then
        printf '0\n' > "$capture_dir/$name.exit"
    else
        local result=$?
        printf '%s\n' "$result" > "$capture_dir/$name.exit"
        echo "preflight capture failed: $name ($result)" >&2
        exit "$result"
    fi
}

capture adb-devices timeout 15s "$adb" devices -l
capture adb-boot timeout 15s "$adb" -s gts9wifi-0001 shell \
    'cat /proc/sys/kernel/random/boot_id; id; cat /proc/uptime'
capture wifi-boot timeout 15s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime'
capture ncm-boot timeout 15s "$ssh_tool" \
    'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime'

capture uname timeout 15s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" 'uname -a'
capture cmdline timeout 15s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" 'cat /proc/cmdline'
capture config-hash timeout 15s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'set -o pipefail; zcat /proc/config.gz | sha256sum'
capture notes-hash timeout 15s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'sha256sum /sys/kernel/notes'
capture partitions timeout 90s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'set -eu; for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/disk/by-partlabel/$n; done'
capture module-directories timeout 20s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'find /usr/lib/modules -maxdepth 1 -type d -print'
capture modules-current timeout 90s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'find /usr/lib/modules/7.2.0-rc3-gts9wifi-dirty -type f -exec sha256sum {} +'
capture modules-test252 timeout 90s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'find /usr/lib/modules/.gts9-test254-original -type f -exec sha256sum {} +'
capture modules-test249 timeout 90s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'find /usr/lib/modules/.gts9-test252-original -type f -exec sha256sum {} +'
capture protected-settings timeout 25s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'set -eu; sha256sum /etc/gts9-usb-net /etc/gts9-usb-adb /usr/libexec/gts9-adbd-can-start /usr/libexec/gts9-usb-adb-hold /usr/libexec/gts9-usb-adb-prepare /usr/libexec/gts9-usb-acm /usr/lib/systemd/system/gts9-usb-acm.service /usr/lib/systemd/system/gts9-usb-adb-hold.service /usr/lib/systemd/system/gts9-usb-adb-prepare.service /usr/lib/android-sdk/platform-tools/adbd /root/.ssh/authorized_keys /etc/ssh/ssh_config /etc/ssh/ssh_host_rsa_key /etc/ssh/ssh_host_ed25519_key.pub /etc/ssh/ssh_host_ecdsa_key.pub /etc/ssh/ssh_host_ed25519_key /etc/ssh/ssh_host_ecdsa_key /etc/ssh/ssh_host_rsa_key.pub /etc/ssh/moduli /etc/ssh/sshd_config'
capture test253-adbd timeout 15s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'set -eu; sha256sum /usr/local/libexec/gts9-adbd-reconnect /usr/libexec/gts9-adbd-run; systemctl show gts9-adbd -p ActiveState -p MainPID -p ExecStart --no-pager'
capture battery timeout 15s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'set -eu; for p in capacity temp voltage_now current_now status health; do printf "%s=" "$p"; cat "/sys/class/power_supply/sm5714-battery/$p"; done; for p in online usb_type; do printf "usb_%s=" "$p"; cat "/sys/class/power_supply/sm5714-usb/$p"; done'
capture dcc-state timeout 15s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'zcat /proc/config.gz | grep -E "^(# CONFIG_HVC_DCC is not set|CONFIG_HVC_DCC=)"; test ! -e /dev/hvc0; test ! -e /sys/class/tty/hvc0; systemctl is-active serial-getty@hvc0.service || true'
capture usb-state timeout 15s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'for f in /sys/class/udc/*/state; do printf "%s=" "$f"; cat "$f"; done; ip -4 -o addr show; systemctl show ssh -p ActiveState --no-pager'
capture failed-units timeout 20s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'systemctl --failed --no-pager --plain'
capture boots timeout 15s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'journalctl --list-boots --no-pager'
capture kernel-journal timeout 60s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'journalctl -b -k --no-pager -o short-monotonic'
capture kernel-journal-json timeout 60s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'journalctl -b -k --no-pager -o json'
capture windows-usb timeout 25s "$powershell" -NoProfile -Command \
    'Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match "VID_0525|VID_0000&PID_0002" } | Select-Object Status,FriendlyName,InstanceId | ConvertTo-Json -Compress'
capture final-boot timeout 15s env GTS9_DEVICE="$wifi_addr" "$ssh_tool" \
    'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime'

echo "read-only Test255 preflight captured at $capture_dir"
