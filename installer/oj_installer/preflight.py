"""Preflight checks and target discovery.

Nothing here changes the machine. The engine calls it again before it wipes
anything.
"""

import json
import os
import shutil
import socket
import subprocess

from . import paths


def output(command):
    return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL).strip()


def memory_bytes():
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return 0


def cpu_count():
    try:
        return len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return os.cpu_count() or 1


def firmware_available():
    return "efi" if os.path.isdir("/sys/firmware/efi") else "bios"


def missing_commands():
    return [name for name in paths.REQUIRED_COMMANDS if shutil.which(name) is None]


def network_available(timeout=5):
    host, port = paths.NETWORK_CHECK_URL
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def resolve_disk_size(disk):
    try:
        return int(output(["blockdev", "--getsize64", disk]))
    except (OSError, subprocess.SubprocessError):
        return 0


def is_mounted(disk):
    real = os.path.realpath(disk)
    try:
        with open("/proc/mounts", encoding="utf-8") as handle:
            for line in handle:
                source = line.split()[0]
                if source == real or source.startswith(real):
                    return True
    except OSError:
        pass
    return False


def mount_source(mountpoint):
    try:
        return output(["findmnt", "-no", "SOURCE", mountpoint])
    except (OSError, subprocess.SubprocessError):
        return ""


def live_medium_disks():
    disks = set()
    for mountpoint in ("/iso", "/nix/.ro-store", "/nix/store"):
        source = mount_source(mountpoint)
        if not source.startswith("/dev/"):
            continue
        try:
            parents = output(["lsblk", "-no", "PKNAME", source]).splitlines()
        except (OSError, subprocess.SubprocessError):
            parents = []
        if parents:
            disks.add("/dev/" + parents[0].strip())
        else:
            disks.add(os.path.realpath(source))
    return disks


def stable_disk_path(path):
    target = os.path.realpath(path)
    for candidate in sorted(os.listdir("/dev/disk/by-id")) if os.path.isdir("/dev/disk/by-id") else []:
        full = os.path.join("/dev/disk/by-id", candidate)
        if "-part" in candidate:
            continue
        if os.path.realpath(full) == target:
            return full
    return path


def block_report():
    return json.loads(
        output(
            [
                "lsblk",
                "-J",
                "-b",
                "-o",
                "NAME,PATH,TYPE,SIZE,RM,RO,TRAN,FSTYPE,MOUNTPOINTS,MODEL",
            ]
        )
    )


def _children(node):
    for child in node.get("children") or []:
        yield child
        yield from _children(child)


def disk_candidates():
    """Return eligible install targets with the reason others were skipped."""
    report = block_report()
    live = live_medium_disks()
    eligible = []
    skipped = []
    for node in report.get("blockdevices", []):
        if node.get("type") != "disk":
            continue
        path = node.get("path") or ""
        size = int(node.get("size") or 0)
        reason = None
        if node.get("rm"):
            reason = "removable"
        elif node.get("ro"):
            reason = "read-only"
        elif (node.get("tran") or "").lower() == "usb":
            reason = "USB or external"
        elif size < paths.MIN_DISK_BYTES:
            reason = "smaller than 30 GiB"
        elif os.path.realpath(path) in live:
            reason = "the live medium"
        elif is_mounted(path):
            reason = "mounted"
        else:
            for child in _children(node):
                if any(child.get("mountpoints") or []):
                    reason = "contains a mounted partition"
                    break
                if (child.get("fstype") or "").lower() == "vfat":
                    reason = "contains an existing vfat partition"
                    break
        if reason:
            skipped.append((path or node.get("name") or "unknown", reason))
            continue
        eligible.append(
            {
                "path": stable_disk_path(path),
                "real": os.path.realpath(path),
                "size": size,
                "model": (node.get("model") or "unknown").strip(),
            }
        )
    return eligible, skipped


def free_regions(disk):
    """Return free regions in sectors: [{start, end, bytes}]."""
    try:
        text = output(["parted", "-m", "-s", disk, "unit", "s", "print", "free"])
    except (OSError, subprocess.SubprocessError):
        return []
    sector_size = 512
    regions = []
    for line in text.splitlines():
        fields = line.split(":")
        if len(fields) < 5 or fields[0].strip():
            continue
        if fields[4].strip() != "free":
            continue
        try:
            start = int(fields[1].rstrip("s"))
            end = int(fields[2].rstrip("s"))
        except ValueError:
            continue
        regions.append(
            {
                "start": start,
                "end": end,
                "bytes": (end - start + 1) * sector_size,
            }
        )
    return regions


def firmware_label(base):
    return base.upper()


def summary():
    eligible, skipped = disk_candidates()
    model = "unknown"
    try:
        with open("/sys/class/dmi/id/product_name", encoding="utf-8") as handle:
            model = handle.read().strip() or "unknown"
    except OSError:
        pass
    return {
        "model": model,
        "firmware": firmware_available(),
        "ram": memory_bytes(),
        "cpus": cpu_count(),
        "network": network_available(),
        "missing": missing_commands(),
        "disks": eligible,
        "skipped": skipped,
    }
