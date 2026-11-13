#!/usr/bin/env python3
"""Layout planner checks. Runs without a disk."""

import sys

from oj_installer import disk, paths

GIB = 1024**3
FAILURES = []


def check(name, condition, detail=""):
    if not condition:
        FAILURES.append("{}: {}".format(name, detail or "failed"))


def expect_error(name, start, end, sector, swap):
    try:
        disk.plan_layout(start, end, sector, swap)
    except disk.DiskError:
        return
    FAILURES.append("{}: expected DiskError".format(name))


def positions(layout):
    return [(part["role"], part["start"], part["end"]) for part in layout]


def main():
    sectors = 512
    start = 2048
    end = 30 * GIB // sectors + start
    layout = disk.plan_layout(start, end, sectors, 0)
    check("three partitions", len(layout) == 3, str(positions(layout)))
    check("roles", [part["role"] for part in layout] == [
        disk.ROLE_BIOS_BOOT, disk.ROLE_ESP, disk.ROLE_ROOT
    ])
    check("bios boot 1 MiB", layout[0]["size"] == paths.BIOS_BOOT_BYTES)
    check("esp 4 GiB", layout[1]["size"] == paths.ESP_BYTES)
    check("root ends at region end", layout[2]["end"] == end)
    check("contiguous", all(
        layout[index]["end"] + 1 == layout[index + 1]["start"] for index in range(2)
    ))
    check("root is the remainder", layout[2]["size"] == (end - layout[2]["start"] + 1) * sectors)

    layout = disk.plan_layout(start, end, sectors, 4 * GIB)
    check("swap added", len(layout) == 4)
    check("swap 4 GiB", layout[2]["size"] == 4 * GIB)

    layout = disk.plan_layout(start, start + 60 * GIB // sectors, sectors, disk.swap_bytes("suspend", 16 * GIB))
    check("suspend swap is RAM size", layout[2]["size"] == 16 * GIB)
    check("suspend swap rounds up", disk.swap_bytes("suspend", 3 * GIB) == 4 * GIB)

    layout = disk.plan_layout(1000, end, sectors, 0)
    check("start is aligned", layout[0]["start"] == paths.ALIGN_SECTORS)

    layout = disk.plan_layout(start, end, 4096, 4 * GIB)
    check("4k sector esp", layout[1]["size"] == paths.ESP_BYTES)
    check("4k sector alignment", layout[0]["start"] % paths.ALIGN_SECTORS == 0)

    expect_error("region too small", start, start + 10 * GIB // sectors, sectors, 0)
    expect_error("empty region", start, start, sectors, 0)
    expect_error("zero sector size", start, end, 0, 0)

    check("free region description", "GiB" in disk.describe_region(
        {"start": 2048, "end": 2048 + 1024, "bytes": 1024 * 512}
    ))
    check("no region", disk.describe_region(None) == "not selected")

    if FAILURES:
        for failure in FAILURES:
            print(failure, file=sys.stderr)
        return 1
    print("layout-plan: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
