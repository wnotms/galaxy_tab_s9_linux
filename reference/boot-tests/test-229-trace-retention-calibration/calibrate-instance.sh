#!/bin/sh
# One healthy-boot capacity observation. No dump trigger, reboot or partition IO.
set -eu
expected=${1:?expected boot ID required}
boot=$(cat /proc/sys/kernel/random/boot_id)
[ "$boot" = "$expected" ] || { echo 'boot identity changed' >&2; exit 1; }
[ "$(cat /sys/devices/system/cpu/online)" = '0-7' ] || exit 1
base=/sys/kernel/tracing
instance=$base/instances/gts9-calibration-229
out=/tmp/gts9-trace229-$boot
[ ! -e "$instance" ] && [ ! -e "$out" ] || { echo 'refusing to reuse a capture' >&2; exit 1; }
mkdir "$out"
global_state() {
    for field in current_tracer tracing_on trace_clock set_event buffer_size_kb; do
        echo "=== $field ==="
        cat "$base/$field"
    done
}
global_state > "$out/global-before.txt"
cleanup() {
    status=$?
    trap - EXIT
    set +e
    if [ -d "$instance" ]; then
        echo 0 > "$instance/tracing_on"
        echo 0 > "$instance/events/enable"
        rmdir "$instance"
        echo "$?" > "$out/instance-removal.status"
    fi
    global_state > "$out/global-after.txt"
    echo "$status" > "$out/exit.status"
    exit "$status"
}
trap cleanup EXIT
mkdir "$instance"
echo 0 > "$instance/tracing_on"
echo nop > "$instance/current_tracer"
echo global > "$instance/trace_clock"
echo 1024 > "$instance/buffer_size_kb"
echo 1 > "$instance/options/latency-format"
echo 0 > "$instance/events/enable"
events='csd:csd_queue_cpu csd:csd_function_entry csd:csd_function_exit ipi:ipi_raise ipi:ipi_entry ipi:ipi_exit rcu:rcu_stall_warning'
for event in $events; do
    group=${event%:*}
    name=${event#*:}
    dir=$instance/events/$group/$name
    cat "$dir/format" > "$out/$group-$name.format"
    cat "$dir/filter" > "$out/$group-$name.filter"
    echo 1 > "$dir/enable"
    [ "$(cat "$dir/enable")" = 1 ] || exit 1
done
for field in current_tracer trace_clock buffer_size_kb tracing_cpumask trace_options set_event; do
    cat "$instance/$field" > "$out/$field.txt"
done
cat /proc/sys/kernel/random/boot_id > "$out/boot-id-before.txt"
cat /proc/uptime > "$out/uptime-before.txt"
stats() {
    phase=$1
    for cpu in 0 1 2 3 4 5 6 7; do
        cat "$instance/per_cpu/cpu$cpu/stats" > "$out/cpu$cpu-$phase.stats"
    done
}
markers() {
    phase=$1
    for cpu in 0 1 2 3 4 5 6 7; do
        taskset -c "$cpu" sh -c 'printf "%s\n" "$1" > "$2"' sh \
            "GTS9_T229_${phase}_cpu=$cpu" "$instance/trace_marker"
    done
}
stats before
echo 1 > "$instance/tracing_on"
markers START
echo 'Tracing seven events for 60 seconds in an isolated instance.'
sleep 60
markers END
echo 0 > "$instance/tracing_on"
stats after
cat /proc/uptime > "$out/uptime-after.txt"
cat /proc/sys/kernel/random/boot_id > "$out/boot-id-after.txt"
cat /sys/devices/system/cpu/online > "$out/cpus-after.txt"
cat "$instance/trace" > "$out/trace.txt"
wc -lc "$out/trace.txt"
[ "$(cat "$out/boot-id-after.txt")" = "$expected" ] || exit 1
echo "Capture complete: $out"
