#!/usr/bin/env python3
"""Read the CPU-idle structure out of a compiled DTB.

Why this is a separate program and not a few lines of awk in the shell wrapper:
the first version of `scripts/verify-idle-ablation.sh` parsed the decompiled tree
with awk and got the wrong answer twice in a row - it dropped the second phandle
of `domain-idle-states = <0x30 0x31>` and it counted *lines* where it needed to
count *phandles*.  Both bugs failed safe (they reported a problem), but a parser
that reports the wrong thing on a good DTB is one careless edit away from
reporting the right thing on a bad one.

So the device tree is parsed properly, as a tree, by phandle.  The whole point of
the verifier is to prove that a `/delete-property/` did what it claims on the
*compiled* artifact - guessing at that with text matching defeats the exercise.

Output is a stable, greppable report; the shell wrapper decides pass/fail.

Usage:
    scripts/lib/dtb-idle-states.py DTB
"""

import re
import subprocess
import sys


# The names the pinned sm8550.dtsi gives the three per-CPU states, and the
# suspend parameter all three share.  Recorded here (not looked up) because the
# verifier's job includes noticing if upstream changes them under us.
CPU_STATE_NAMES = (
    "silver-rail-power-collapse",
    "gold-rail-power-collapse",
    "goldplus-rail-power-collapse",
)
CPU_STATE_PARAM = "0x40000004"
CLUSTER_STATE_PARAMS = ("0x41000044", "0x4100c344")


def decompile(dtb):
    """dtc -I dtb -O dts, as text.  Raises if dtc is unavailable or fails."""
    proc = subprocess.run(
        ["dtc", "-I", "dtb", "-O", "dts", dtb],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"dtc failed on {dtb}: {proc.stderr.strip() or 'no diagnostic'}"
        )
    return proc.stdout


def parse_tree(dts_text):
    """Return (nodes, phandles).

    `nodes` maps a node's full path to a dict of its properties, where a property
    value is kept as the raw text between the angle brackets (or the raw token
    for string/boolean properties).  `phandles` maps a phandle value to a path.

    This is deliberately a small brace-aware scanner rather than a real DTS
    parser: the output of `dtc -O dts` is machine-generated and regular, and a
    dependency-free scanner is easier to audit than a grammar.  It still tracks
    nesting properly, which is the property the awk version lacked.
    """
    nodes = {}
    phandles = {}
    # Strip C-style comments; dtc emits them for /delete-property/ provenance.
    text = re.sub(r"/\*.*?\*/", "", dts_text, flags=re.S)

    # Walk the tree keeping a path stack driven by brace depth.  Node headers are
    # `name {` or `name@addr {`; every other `... ;` inside a node is a property.
    stack = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # A node opens: `<name> {`  (possibly with a label prefix like `foo: bar {`)
        m = re.match(r"^(?:[A-Za-z_][\w-]*:\s*)?([^\s{]+)\s*\{$", line)
        if m:
            name = m.group(1)
            # The root is `/. It is NOT pushed onto the stack: pushing it made
            # every descendant path start with `//`, which silently sent the
            # root's own properties to a phantom `//` node and made `model`,
            # `compatible`, `qcom,board-id` and `qcom,msm-id` all read as
            # ABSENT on a perfectly good device tree.
            if name == "/" and not stack:
                nodes.setdefault("/", {})
                continue
            stack.append(name)
            nodes.setdefault("/" + "/".join(stack), {})
            continue

        if line == "};":
            if stack:
                stack.pop()
            continue

        # A property: `name = <...>;`, `name = "str";`, or a bare boolean.
        m = re.match(r"^([\w,._+#-]+)\s*=\s*(.*?);$", line)
        if m:
            # With an empty stack we are still at the root, so the path is "/"
            # rather than "".
            path = "/" + "/".join(stack)
            prop, value = m.group(1), m.group(2).strip()
            if value.startswith("<") and value.endswith(">"):
                value = value[1:-1].strip()
            elif value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            nodes.setdefault(path, {})[prop] = value
            continue

        m = re.match(r"^([\w,._+#-]+);$", line)
        if m:
            nodes.setdefault("/" + "/".join(stack), {})[m.group(1)] = ""

    for path, props in nodes.items():
        ph = props.get("phandle")
        if ph is not None:
            phandles[normalise_phandle(ph)] = path
    return nodes, phandles


def normalise_phandle(value):
    """`0x2c` and `<0x2c>` both mean the same phandle."""
    v = value.strip().strip("<>").strip()
    try:
        return int(v, 0)
    except ValueError:
        return v


def phandle_list(value):
    """Every phandle in a property whose value is a list of cells."""
    return [int(tok, 0) for tok in re.findall(r"0x[0-9a-fA-F]+|\b\d+\b", value)]


def find_node(nodes, suffix):
    """The one node path ending in `/<suffix>` (or equal to it)."""
    hits = [p for p in nodes if p == f"/{suffix}" or p.endswith(f"/{suffix}")]
    return hits


def suspend_param(nodes, path):
    return nodes.get(path, {}).get("arm,psci-suspend-param")


def main(argv):
    if len(argv) != 2:
        print("usage: dtb-idle-states.py DTB", file=sys.stderr)
        return 2
    dtb = argv[1]

    try:
        dts = decompile(dtb)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    nodes, phandles = parse_tree(dts)

    print(f"dtb={dtb}")

    # --- the cluster power domain --------------------------------------------
    pd_hits = find_node(nodes, "power-domain-cluster")
    if not pd_hits:
        print("cluster_pd=ABSENT")
        print("error: no power-domain-cluster node", file=sys.stderr)
        return 1
    pd_path = pd_hits[0]
    print(f"cluster_pd_node={pd_path}")

    # --- the per-CPU power domains -------------------------------------------
    cpu_pd = sorted(
        p for p in nodes if re.search(r"/power-domain-cpu\d+$", p)
    )
    print(f"cpu_pd_count={len(cpu_pd)}")

    # --- resolve what each domain references ---------------------------------
    def referenced_states(domain_path):
        """The suspend params of the states this domain references, in order."""
        raw = nodes.get(domain_path, {}).get("domain-idle-states")
        if raw is None:
            return None  # property absent
        out = []
        for ph in phandle_list(raw):
            target = phandles.get(ph)
            if target is None:
                out.append(f"unresolved:{ph:#x}")
            else:
                out.append(suspend_param(nodes, target) or "no-param")
        return out

    cluster_states = referenced_states(pd_path)
    if cluster_states is None:
        print("cluster_states=")          # property absent: no cluster states
    else:
        print("cluster_states=" + " ".join(cluster_states))

    # Per-CPU references: each must resolve to exactly one state.
    cpu_refs = {}
    for path in cpu_pd:
        states = referenced_states(path)
        cpu_refs[path] = states
        n = 0 if states is None else len(states)
        print(f"cpu_pd_state_count:{path.rsplit('/', 1)[-1]}={n}")

    # --- the CPU state definitions -------------------------------------------
    cpu_names = []
    for path, props in nodes.items():
        name = props.get("idle-state-name")
        if name in CPU_STATE_NAMES:
            cpu_names.append(name)
    for name in CPU_STATE_NAMES:
        print(f"cpu_state_name:{name}={'present' if name in cpu_names else 'MISSING'}")

    n_cpu_param = sum(
        1 for p, props in nodes.items()
        if props.get("arm,psci-suspend-param") == CPU_STATE_PARAM
        and props.get("compatible") == "arm,idle-state"
    )
    print(f"cpu_states_with_shared_param={n_cpu_param}")

    n_cluster_param = sum(
        1 for p, props in nodes.items()
        if props.get("arm,psci-suspend-param") in CLUSTER_STATE_PARAMS
        and props.get("compatible") == "domain-idle-state"
    )
    print(f"cluster_state_definitions={n_cluster_param}")

    # --- the machine identity, so a wrong DTB cannot pass -------------------
    root = nodes.get("/", {})
    print(f"model={root.get('model', 'ABSENT')}")
    compatible = root.get("compatible", "")
    print(f"compatible={compatible}")
    print(f"board_id={'present' if 'qcom,board-id' in root else 'ABSENT'}")
    print(f"msm_id={'present' if 'qcom,msm-id' in root else 'ABSENT'}")

    # --- ABL labels, which live in __symbols__, not in the tree -------------
    for label in ("qcom_tzlog", "arch_timer", "qcom_scm"):
        print(f"symbol:{label}={'present' if re.search(rf'\b{label} = ', dts) else 'MISSING'}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
