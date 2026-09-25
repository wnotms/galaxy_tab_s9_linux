#!/usr/bin/env bash
# Shared host glue for the console helpers.  Source it, do not run it.
#
# The repository is developed inside WSL but the serial port belongs to Windows,
# which creates exactly two problems for every PowerShell helper:
#
#   1. `-File` rejects a UNC path, so a script living on the WSL filesystem
#      cannot be run from \\wsl.localhost\... ; it must be staged into a real
#      Windows directory first.
#   2. `-File` binds an array parameter to only ONE argument, so
#      `-Commands a,b` silently becomes `-Commands a` plus a stray positional.
#      Only `-Command` parses an array literal, so that is the form used here.
#
# On Windows proper both problems disappear and the native path is used, so a
# Windows checkout keeps working.  Detection is by the existence of the Windows
# PowerShell binary under /mnt/c, which only exists inside WSL.
#
# Provides:
#   gts9_ps_exe                 path to the PowerShell to run
#   gts9_ps_in_wsl              0 when running on Windows, 1 inside WSL
#   gts9_ps_quote <s>           PowerShell single-quoted literal for <s>
#   gts9_ps_array <s...>        PowerShell @('a','b') literal for the arguments
#   gts9_ps_stage <file.ps1>    echoes a path PowerShell can actually execute
#   gts9_ps_exec <file.ps1> <ps-args...>
#                               runs the script with args already in PowerShell
#                               syntax (built with gts9_ps_quote / gts9_ps_array)

GTS9_PS_EXE_WSL=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
GTS9_PS_STAGE_WSL=/mnt/c/Users/ms/AppData/Local/Temp/gts9-scripts
GTS9_PS_STAGE_WIN='C:\Users\ms\AppData\Local\Temp\gts9-scripts'

gts9_ps_in_wsl() { [ -x "$GTS9_PS_EXE_WSL" ] && echo 1 || echo 0; }

gts9_ps_exe() {
	if [ "$(gts9_ps_in_wsl)" = "1" ]; then
		printf '%s' "$GTS9_PS_EXE_WSL"
	else
		printf '%s' "${GTS9_POWERSHELL:-powershell.exe}"
	fi
}

# PowerShell single-quoted literal: an embedded quote is doubled.
gts9_ps_quote() { printf "'%s'" "${1//\'/\'\'}"; }

gts9_ps_array() {
	local out="" a
	for a in "$@"; do
		[ -n "$out" ] && out+=","
		out+="$(gts9_ps_quote "$a")"
	done
	printf '@(%s)' "$out"
}

# Restate a filesystem path in the form PowerShell expects on this host.
gts9_ps_winpath() {
	if [ "$(gts9_ps_in_wsl)" = "1" ]; then
		printf '%s' "$1"
	else
		case "$1" in
		/mnt/*) printf '%s' "$1" | sed -E 's#^/mnt/([a-zA-Z])/#\1:/#' ;;
		/[a-zA-Z]/*) printf '%s' "$1" | sed -E 's#^/([a-zA-Z])/#\1:/#' ;;
		*) printf '%s' "$1" ;;
		esac
	fi
}

# Echo a path to <file.ps1> that PowerShell on this host can execute.
gts9_ps_stage() {
	local src=$1 name
	name=$(basename "$src")
	if [ "$(gts9_ps_in_wsl)" = "1" ]; then
		mkdir -p "$GTS9_PS_STAGE_WSL"
		cp "$src" "$GTS9_PS_STAGE_WSL/$name"
		printf '%s' "$GTS9_PS_STAGE_WIN\\$name"
	else
		printf '%s' "$(gts9_ps_winpath "$src" | tr '/' '\\')"
	fi
}

# Run a staged helper.  $1 is the local .ps1; the rest are already in PowerShell
# syntax, e.g. "-Seconds 60 -Port $(gts9_ps_quote COM19)".
gts9_ps_exec() {
	local src=$1; shift
	local win
	win=$(gts9_ps_stage "$src")
	exec "$(gts9_ps_exe)" -NoProfile -ExecutionPolicy Bypass \
		-Command "& $(gts9_ps_quote "$win") $*"
}
