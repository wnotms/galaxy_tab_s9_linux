#!/bin/sh
# Test323 paired modules, unique backup slots; leave other registered backup slots unchanged.
# Release-root module archive adapter. Offline TWRP maintenance only. The caller verifies recovery and partition identity.
set -eu
root=${1:?mounted Debian root}
mode=${2:?install or restore}
expected=${3:?desired manifest}
archive=${4:-}
release=7.2.0-rc3-gts9wifi-dirty
base=$root/usr/lib/modules
current=$base/$release
saved=$base/.gts9-test323-original
stage=$base/.gts9-test323-stage
tested=$base/.gts9-test323-tested
test "$(cat "$root/etc/machine-id")" = 3c2a1b8f2d624db4b5ffdc836050fcf6
test -d "$base"
verify() {
    directory=$1
    manifest=$2
    test "$(find "$directory" -type f | wc -l)" -eq 181
    test "$(wc -l < "$manifest")" -eq 181
    (cd "$directory" && sha256sum -c "$manifest")
    links=$(find "$directory" -type l | wc -l)
    case $links in
        0) ;;
        1) test -L "$directory/build"
           test "$(readlink "$directory/build")" = /home/ms/Samsung/galaxy_tab_s9_linux/.work/build/linux-out ;;
        *) exit 1 ;;
    esac
}
case $mode in
    install)
        original=${5:?original manifest}
        test ! -e "$saved" && test ! -e "$stage" && test ! -e "$tested"
        verify "$current" "$original"
        mkdir -p "$stage/lib/modules"
        # Current build-kernel archives are rooted at $release, not lib/modules.
        # Refuse another layout before any current-directory rename.
        tar -tzf "$archive" > "$stage/archive-members"
        while IFS= read -r member; do
            case $member in
                "$release"/|"$release"/*) ;;
                *) echo "unexpected module archive root: $member" >&2; exit 1 ;;
            esac
            case $member in
                */../*|*/..|*/./*|*/.|*//*) exit 1 ;;
            esac
        done < "$stage/archive-members"
        rm "$stage/archive-members"
        tar -xzf "$archive" -C "$stage/lib/modules"
        verify "$stage/lib/modules/$release" "$expected"
        mv "$current" "$saved"
        if ! mv "$stage/lib/modules/$release" "$current"; then
            mv "$saved" "$current"
            exit 1
        fi
        sync
        verify "$current" "$expected"
        rmdir "$stage/lib/modules" "$stage/lib" "$stage"
        ;;
    restore)
        verify "$saved" "$expected"
        test ! -e "$tested"
        if test -e "$current"; then mv "$current" "$tested"; fi
        if ! mv "$saved" "$current"; then
            if test -d "$tested"; then mv "$tested" "$current"; fi
            exit 1
        fi
        sync
        verify "$current" "$expected"
        ;;
    *) exit 2 ;;
esac
