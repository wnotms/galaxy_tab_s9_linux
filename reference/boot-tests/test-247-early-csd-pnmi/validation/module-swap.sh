#!/bin/sh
# Caller must independently verify the TWRP identity and mounted Debian device.
# This file only changes the one named module directory after complete hashing.
set -eu
root=${1:?mounted Debian root required}
mode=${2:?install or restore required}
expected=${3:?manifest required}
archive=${4:-}
release=7.2.0-rc3-gts9wifi-dirty
base=$root/usr/lib/modules
current=$base/$release
saved=$base/.gts9-test247-original
stage=$base/.gts9-test247-stage
tested=$base/.gts9-test247-tested
test "$(cat "$root/etc/machine-id")" = 3c2a1b8f2d624db4b5ffdc836050fcf6
test -d "$base"
verify() {
    directory=$1
    manifest=$2
    count=$(wc -l < "$manifest")
    test "$(find "$directory" -type f | wc -l)" -eq "$count"
    (cd "$directory" && sha256sum -c "$manifest")
    test "$(find "$directory" -type l | wc -l)" -eq 1
    test "$(readlink "$directory/build")" = /home/ms/Samsung/galaxy_tab_s9_linux/.work/build/linux-out
}
case $mode in
    install)
        original=${5:?original manifest required}
        test ! -e "$saved"
        test ! -e "$stage"
        test ! -e "$tested"
        verify "$current" "$original"
        mkdir "$stage"
        tar -xf "$archive" -C "$stage"
        verify "$stage/$release" "$expected"
        mv "$current" "$saved"
        if ! mv "$stage/$release" "$current"; then
            mv "$saved" "$current"
            exit 1
        fi
        sync
        verify "$current" "$expected"
        rmdir "$stage"
        ;;
    restore)
        verify "$saved" "$expected"
        test ! -e "$tested"
        # Handles interruption after the first installation rename too.
        if test -e "$current"; then mv "$current" "$tested"; fi
        if ! mv "$saved" "$current"; then
            if test -d "$tested"; then mv "$tested" "$current"; fi
            exit 1
        fi
        sync
        verify "$current" "$expected"
        # Retain the used candidate for inspection; cleanup is a separate action.
        ;;
    *) exit 2 ;;
esac
