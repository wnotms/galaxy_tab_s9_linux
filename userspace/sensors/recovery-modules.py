#!/usr/bin/env python3
"""Namespace-explicit offline recovery command; caller verifies TWRP/root identity."""
import re
import shlex


def command(root, release, namespace, baseline_manifest, candidate_manifest, machine_id):
    if not re.fullmatch(r'gts9-test[1-9][0-9]{2,4}',namespace):raise ValueError('invalid recovery namespace')
    if not re.fullmatch(r'[0-9a-f]{32}',machine_id):raise ValueError('invalid machine identity')
    if not re.fullmatch(r'[A-Za-z0-9._+-]+',release):raise ValueError('invalid release')
    for path in (root,baseline_manifest,candidate_manifest):
        if not path.startswith('/') or any(x in ('.','..','') for x in path.split('/')[1:]):raise ValueError('unsafe absolute path')
    quote=shlex.quote
    base=root+'/usr/lib/modules';current=base+'/'+release;saved=base+'/.'+namespace+'-original';tested=base+'/.'+namespace+'-tested'
    return f'''set -eu
root={quote(root)}
current={quote(current)}
saved={quote(saved)}
tested={quote(tested)}
baseline={quote(baseline_manifest)}
candidate={quote(candidate_manifest)}
test "$(cat "$root/etc/machine-id")" = {quote(machine_id)}
verify() {{
    test -d "$1"
    test ! -L "$1"
    test "$(find "$1" -type f | wc -l)" -eq 181
    test "$(wc -l < "$2")" -eq 181
    (cd "$1" && sha256sum -c "$2")
    links=$(find "$1" -type l | wc -l)
    case $links in
        0) ;;
        1) test -L "$1/build"
           test "$(readlink "$1/build")" = /home/ms/Samsung/galaxy_tab_s9_linux/.work/build/linux-out ;;
        *) exit 1 ;;
    esac
}}
if test -e "$saved" || test -L "$saved"; then
    verify "$saved" "$baseline"
    verify "$current" "$candidate"
    test ! -e "$tested"
    test ! -L "$tested"
    mv "$current" "$tested"
    if ! mv "$saved" "$current"; then
        mv "$tested" "$current"
        exit 1
    fi
    sync
fi
verify "$current" "$baseline"
echo MODULE_BASELINE_VERIFIED_{namespace}
'''
