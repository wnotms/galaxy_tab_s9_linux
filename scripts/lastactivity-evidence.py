#!/usr/bin/env python3
"""Validate bounded last-activity snapshots, without inferring missing events."""
import argparse
import json
from pathlib import Path
import re

UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"


def parse(text, capture_id):
    if not re.fullmatch(UUID, capture_id):
        raise ValueError("invalid expected capture ID")
    lines = []
    active = False
    ended = False
    cpus = {}
    records = []
    trigger = None
    for raw in text.splitlines():
        pos = raw.find("GTS9_LA_")
        if pos < 0:
            continue
        line = raw[pos:]
        if line.startswith("GTS9_LA_BEGIN "):
            if f"id={capture_id} " not in line:
                if active:
                    raise ValueError("interleaved capture")
                continue
            if active or ended:
                raise ValueError("duplicate snapshot")
            m = re.fullmatch(rf"GTS9_LA_BEGIN id={capture_id} trigger=(manual|rcu) ns=(\d+) schema=1 cpus=8 events=6 complete_history=0", line)
            if not m:
                raise ValueError("invalid begin marker")
            trigger = m[1]
            active = True
        if not active:
            continue
        lines.append(line)
        if line.startswith("GTS9_LA_CPU "):
            m = re.fullmatch(rf"GTS9_LA_CPU id={capture_id} cpu=([0-7]) valid=([01]) seq=(\d+) nested_dropped=(-?\d+)", line)
            if not m or int(m[1]) in cpus:
                raise ValueError("bad or repeated CPU record")
            cpu = int(m[1])
            cpus[cpu] = {"valid": bool(int(m[2])), "seq": int(m[3]), "nested_dropped": int(m[4])}
            if cpus[cpu]["valid"] and cpus[cpu]["seq"] % 2:
                raise ValueError("odd writer sequence marked valid")
        elif line.startswith("GTS9_LA_EVENT "):
            m = re.fullmatch(r"GTS9_LA_EVENT cpu=([0-7]) kind=([0-5]) count=(\d+) ns=(\d+) a=([0-9a-f]{16}) b=([0-9a-f]{16}) c=([0-9a-f]{16})", line)
            if not m:
                raise ValueError("invalid event")
            cpu, kind, count, ns = map(int, m.groups()[:4])
            if cpu not in cpus or not cpus[cpu]["valid"]:
                raise ValueError("event from unverified CPU")
            if any(r["cpu"] == cpu and r["kind"] == kind for r in records):
                raise ValueError("duplicate event")
            if count >= 2**64 or ns >= 2**64 or (count == 0 and (ns or any(int(v, 16) for v in m.groups()[4:]))):
                raise ValueError("invalid event counters")
            records.append(dict(cpu=cpu, kind=kind, count=count, ns=ns, a=m[5], b=m[6], c=m[7]))
        elif line.startswith("GTS9_LA_END "):
            m = re.fullmatch(rf"GTS9_LA_END id={capture_id} records=(\d+) complete_history=0", line)
            if not m or int(m[1]) != len(records):
                raise ValueError("missing or inconsistent footer")
            active, ended = False, True
        elif not line.startswith("GTS9_LA_BEGIN "):
            raise ValueError("unexpected snapshot marker")
    if not ended or active or set(cpus) != set(range(8)):
        raise ValueError("incomplete snapshot")
    for cpu, state in cpus.items():
        if sum(r["cpu"] == cpu for r in records) != (6 if state["valid"] else 0):
            raise ValueError("missing CPU events")
    return {"capture_id": capture_id, "trigger": trigger, "cpus": cpus,
            "records": records, "snapshot_lines": len(lines),
            "snapshot_text_bytes": sum(len(line.encode()) + 1 for line in lines),
            "complete_history": False, "missing_event_inference": "inconclusive",
            "root_cause": "not_established"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--capture-id", required=True)
    args = parser.parse_args()
    print(json.dumps(parse(args.log.read_text(), args.capture_id), indent=2))


if __name__ == "__main__":
    main()
