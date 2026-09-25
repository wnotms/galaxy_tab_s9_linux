#!/usr/bin/env bash
# ssh and scp to the tablet over the USB network function.
#
# The link comes from the NCM function the gts9 gadget adds (see
# docs/FAST_DEBUG_CHANNEL.md).  The device is put on 169.254.0.0/16 on purpose:
# Windows gives the adapter an APIPA address there on its own, so no static IPv4
# configuration and no elevation are needed on the host, and WSL2 reaches it
# through the Windows host.
#
#   scripts/gts9-ssh.sh 'dmesg | tail -20'          # remote command
#   scripts/gts9-ssh.sh                             # interactive shell
#   scripts/gts9-ssh.sh --push ./local.bin /tmp/x   # scp up
#   scripts/gts9-ssh.sh --pull /var/log/x ./x       # scp down
#
#   GTS9_DEVICE=192.168.42.1 scripts/gts9-ssh.sh uptime
set -euo pipefail

DEV=${GTS9_DEVICE:-169.254.42.1}
KEY=${GTS9_SSH_KEY:-$HOME/.ssh/gts9_ed25519}
REMOTE_USER=${GTS9_SSH_USER:-root}

if [ ! -f "$KEY" ]; then
	echo "gts9-ssh: no key at $KEY" >&2
	echo "  create:  ssh-keygen -t ed25519 -N '' -f $KEY" >&2
	echo "  install: scripts/gts9-debug-channel.sh install-key" >&2
	exit 2
fi

common=(-i "$KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
	-o ConnectTimeout=10 -o LogLevel=ERROR)

case "${1:-}" in
--push)
	[ "$#" -eq 3 ] || { echo "usage: gts9-ssh.sh --push LOCAL REMOTE" >&2; exit 2; }
	exec scp "${common[@]}" "$2" "$REMOTE_USER@$DEV:$3"
	;;
--pull)
	[ "$#" -eq 3 ] || { echo "usage: gts9-ssh.sh --pull REMOTE LOCAL" >&2; exit 2; }
	exec scp "${common[@]}" "$REMOTE_USER@$DEV:$2" "$3"
	;;
--help | -h)
	sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
	exit 0
	;;
esac

if [ "$#" -eq 0 ]; then
	exec ssh "${common[@]}" "$REMOTE_USER@$DEV"
fi

exec ssh "${common[@]}" "$REMOTE_USER@$DEV" "$@"
