#!/usr/bin/env python3
"""Offline resolved-config gate; no build, runtime sysctl or device operations."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re


# These are kernel prerequisites, not proof of a configured/running daemon.
# Also keep the existing prerequisites explicit so seed changes cannot remove
# them unnoticed. Reasons/categories are exported into the audit table.
GROUPS = (
    ("UPower / Docker rootless", "systemd PrivateUsers= and rootless user namespaces",
     "USER_NS"),
    ("Docker required", "OCI isolation, IPC, seccomp, keys and overlay2 prerequisites",
     "NAMESPACES UTS_NS IPC_NS PID_NS NET_NS POSIX_MQUEUE SECCOMP SECCOMP_FILTER "
     "KEYS OVERLAY_FS TMPFS EXT4_FS EXT4_FS_POSIX_ACL EXT4_FS_SECURITY"),
    ("Docker resource control", "cgroup v2 CPU/cpuset/memory/pids/io and device BPF support",
     "CGROUPS CGROUP_CPUACCT CGROUP_DEVICE CGROUP_FREEZER CGROUP_SCHED "
     "CGROUP_PIDS CPUSETS MEMCG BLK_CGROUP CGROUP_BPF FAIR_GROUP_SCHED "
     "CFS_BANDWIDTH BLK_DEV_THROTTLING"),
    ("Docker resource control", "optional perf integration and legacy cgroup packet classifier",
     "CGROUP_PERF NET_CLS_CGROUP"),
    ("Docker networking", "common Docker virtual networks and bridge VLAN support",
     "INET IPV6 VETH BRIDGE BRIDGE_NETFILTER VLAN_8021Q MACVLAN IPVLAN VXLAN "
     "BRIDGE_VLAN_FILTERING"),
    ("Docker networking", "connection tracking, NAT and existing x_tables extensions",
     "NETFILTER NETFILTER_ADVANCED NF_CONNTRACK NF_NAT NF_NAT_MASQUERADE "
     "NETFILTER_XTABLES NETFILTER_XT_TARGET_MASQUERADE NETFILTER_XT_MATCH_ADDRTYPE "
     "NETFILTER_XT_MATCH_CONNTRACK NETFILTER_XT_MARK NETFILTER_XT_NAT NETFILTER_XT_TARGET_REDIRECT"),
    ("Docker networking", "Debian iptables-nft/native nftables families, NAT and compatibility",
     "NF_TABLES NF_TABLES_INET NF_TABLES_IPV4 NF_TABLES_IPV6 NFT_CT NFT_NAT "
     "NFT_MASQ NFT_REDIR NFT_COMPAT NFT_FIB_IPV4 NFT_FIB_IPV6 NFT_FIB"),
    ("Docker networking", "Linux 7.2 legacy evaluator parents and IPv4/IPv6 tables fallback",
     "NETFILTER_XTABLES_LEGACY IP_NF_IPTABLES IP_NF_IPTABLES_LEGACY IP_NF_FILTER "
     "IP_NF_MANGLE IP_NF_RAW IP_NF_NAT IP_NF_TARGET_MASQUERADE IP6_NF_IPTABLES "
     "IP6_NF_IPTABLES_LEGACY IP6_NF_FILTER IP6_NF_MANGLE IP6_NF_RAW IP6_NF_NAT "
     "IP6_NF_TARGET_MASQUERADE"),
    ("Docker networking", "minimal Swarm/IPVS TCP/UDP, conntrack and round-robin prerequisites",
     "IP_VS IP_VS_NFCT IP_VS_PROTO_TCP IP_VS_PROTO_UDP IP_VS_RR NETFILTER_XT_MATCH_IPVS"),
)
FEATURES = {"CONFIG_" + name: {"category": category, "reason": reason}
            for category, reason, names in GROUPS for name in names.split()}
REQUIRED_Y = frozenset(FEATURES)
PRESERVE_Y = frozenset(("CONFIG_BATTERY_SM5714", "CONFIG_QCOM_SPMI_ADC5_GEN3"))
REQUIRED_OFF = frozenset(("CONFIG_HVC_DCC",))
BLOCKED_NEW_ON = frozenset("CONFIG_" + name for name in (
    "IP_NF_ARPTABLES IP_NF_ARPFILTER IP_NF_ARP_MANGLE IP_NF_SECURITY "
    "IP_NF_TARGET_NETMAP IP_NF_TARGET_REDIRECT IP_NF_TARGET_REJECT "
    "IP6_NF_TARGET_REJECT IP6_NF_MATCH_RPFILTER NETFILTER_XT_TARGET_DSCP "
    "NETFILTER_XT_TARGET_NOTRACK NETFILTER_XT_TARGET_TPROXY NETFILTER_XT_TARGET_TRACE "
    "NETFILTER_XT_TARGET_CT"
).split())


def read_config(text):
    """Preserve absent vs explicit n for exact diffs; reject conflicting entries."""
    result = {}
    for line in text.splitlines():
        match = re.fullmatch(r"(CONFIG_\w+)=(.*)", line)
        disabled = re.fullmatch(r"# (CONFIG_\w+) is not set", line)
        if match:
            name, value = match.groups()
        elif disabled:
            name, value = disabled[1], "n"
        else:
            continue
        if name in result and result[name] != value:
            raise ValueError(f"conflicting configuration for {name}")
        result[name] = value
    return result


def delta(before, after):
    return {name: [before.get(name, "absent"), after.get(name, "absent")]
            for name in sorted(before.keys() | after.keys())
            if before.get(name) != after.get(name)}


def verify(text, baseline=None, expected_delta=None):
    config = read_config(text)
    errors = [f"{name}: expected y, got {config.get(name, 'absent')}"
              for name in sorted(REQUIRED_Y | PRESERVE_Y)
              if config.get(name) != "y"]
    errors += [f"{name}: must remain disabled"
               for name in sorted(REQUIRED_OFF | BLOCKED_NEW_ON)
               if config.get(name) not in (None, "n")]
    if expected_delta is not None and baseline is None:
        raise ValueError("expected delta requires a baseline")
    changes = delta(read_config(baseline), config) if baseline is not None else None
    unexpected = None
    missing = None
    if expected_delta is not None:
        unexpected = {k: v for k, v in changes.items() if expected_delta.get(k) != v}
        missing = {k: v for k, v in expected_delta.items() if changes.get(k) != v}
        if unexpected or missing:
            errors.append("configuration delta differs from reviewed exact delta")
    return {"valid": not errors, "errors": errors,
            "config_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "required_y_count": len(REQUIRED_Y), "dcc_absent": not any(
                config.get(k) in ("y", "m") for k in REQUIRED_OFF),
            "config_delta": changes, "unexpected_delta": unexpected,
            "missing_expected_delta": missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--expected-delta", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--diff", type=Path)
    args = parser.parse_args()
    try:
        # Path.read_text normalizes CRLF. Build configs use LF; device configs
        # should be byte-checked against the accepted manifest before this gate.
        text = args.config.read_text()
        baseline = args.baseline.read_text() if args.baseline else None
        expected = json.loads(args.expected_delta.read_text()) if args.expected_delta else None
        if args.diff and baseline is None:
            raise ValueError("--diff requires --baseline")
        result = verify(text, baseline, expected)
        if args.diff:
            args.diff.parent.mkdir(parents=True, exist_ok=True)
            args.diff.write_text("".join(difflib.unified_diff(
                baseline.splitlines(True), text.splitlines(True),
                fromfile=str(args.baseline), tofile=str(args.config))))
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, indent=2) + "\n")
    except (OSError, ValueError) as error:
        parser.exit(2, f"container config gate: {error}\n")
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
