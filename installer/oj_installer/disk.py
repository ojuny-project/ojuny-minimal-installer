"""Disk planning, partitioning, formatting and mounting.

The layout is a pure function of the region and the choices, so the checks can
run it without a disk.
"""

import os
import stat
import subprocess

from . import paths, preflight

ROLE_BIOS_BOOT = "bios-boot"
ROLE_ESP = "esp"
ROLE_SWAP = "swap"
ROLE_ROOT = "root"

TYPE_BIOS_BOOT = "EF02"
TYPE_ESP = "EF00"
TYPE_SWAP = "8200"
TYPE_ROOT = "8300"


class DiskError(Exception):
    pass


def run(command, input_text=None):
    result = subprocess.run(
        command,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0:
        raise DiskError(
            "command failed ({}): {}\n{}".format(
                result.returncode, " ".join(str(part) for part in command), result.stdout
            )
        )
    return result.stdout


def sector_size(disk):
    try:
        return int(preflight.output(["blockdev", "--getss", disk]))
    except (OSError, subprocess.SubprocessError, ValueError):
        return paths.SECTOR_BYTES


def total_sectors(disk):
    size = preflight.resolve_disk_size(disk)
    return size // sector_size(disk)


def swap_bytes(swap_choice, memory):
    if swap_choice == "small":
        return paths.SMALL_SWAP_BYTES
    if swap_choice == "suspend":
        gib = 1024**3
        return max(paths.SMALL_SWAP_BYTES, ((memory + gib - 1) // gib) * gib)
    return 0


def plan_layout(start, end, sector_bytes, swap_size, align=paths.ALIGN_SECTORS):
    """Plan partitions inside an inclusive sector range.

    Returns a list of {role, start, end, size, type}. Raises DiskError when the
    region cannot hold the fixed partitions plus a usable root.
    """
    if sector_bytes <= 0:
        raise DiskError("sector size must be positive")
    start = max(align, _align_up(start, align))
    if end <= start:
        raise DiskError("region is empty")

    sectors = []
    cursor = start

    bios_boot = _align_up(paths.BIOS_BOOT_BYTES // sector_bytes, align)
    bios_end = cursor + bios_boot - 1
    sectors.append({"role": ROLE_BIOS_BOOT, "start": cursor, "end": bios_end,
                    "size": bios_boot * sector_bytes, "type": TYPE_BIOS_BOOT})
    cursor = bios_end + 1

    esp_sectors = _align_up(paths.ESP_BYTES // sector_bytes, align)
    esp_end = cursor + esp_sectors - 1
    sectors.append({"role": ROLE_ESP, "start": cursor, "end": esp_end,
                    "size": esp_sectors * sector_bytes, "type": TYPE_ESP})
    cursor = esp_end + 1

    if swap_size > 0:
        swap_sectors = _align_up(swap_size // sector_bytes, align)
        swap_end = cursor + swap_sectors - 1
        sectors.append({"role": ROLE_SWAP, "start": cursor, "end": swap_end,
                        "size": swap_sectors * sector_bytes, "type": TYPE_SWAP})
        cursor = swap_end + 1

    minimum_root = 20 * 1024**3 // sector_bytes
    if end - cursor + 1 < minimum_root:
        raise DiskError(
            "region is too small: the fixed partitions leave less than 20 GiB for the root filesystem"
        )
    sectors.append({"role": ROLE_ROOT, "start": cursor, "end": end,
                    "size": (end - cursor + 1) * sector_bytes, "type": TYPE_ROOT})
    return sectors


def _align_up(value, align):
    remainder = value % align
    return value if remainder == 0 else value + align - remainder


def describe_region(region):
    if not region:
        return "not selected"
    return "sectors {} to {} ({:.1f} GiB)".format(
        region["start"], region["end"], region["bytes"] / 1024**3
    )


def describe_free_region(settings):
    if settings.disk_mode != "free":
        return "unused (erase mode)"
    region = resolve_free_region(settings)
    return describe_region(region)


def resolve_free_region(settings):
    """Pick the largest free region on the target disk that fits the minimum."""
    if settings.disk_mode != "free" or not settings.disk:
        return None
    cached = settings.extras.get("free_region")
    if cached and cached.get("disk") == settings.disk:
        return cached
    regions = [
        region
        for region in preflight.free_regions(settings.disk)
        if region["bytes"] >= paths.MIN_DISK_BYTES
    ]
    if not regions:
        return None
    region = max(regions, key=lambda item: item["bytes"])
    region = dict(region, disk=settings.disk)
    settings.disk_free_start = region["start"]
    settings.disk_free_end = region["end"]
    settings.extras["free_region"] = region
    return region


def partition_path(disk, number):
    name = os.path.realpath(disk).rstrip("/")
    if name[-1].isdigit():
        return "{}p{}".format(name, number)
    return "{}{}".format(name, number)


def existing_partition_numbers(disk):
    try:
        text = run(["sgdisk", "--print", disk])
    except DiskError:
        return []
    numbers = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0].isdigit():
            numbers.append(int(fields[0]))
    return sorted(numbers)


def create_partitions(disk, layout, mode):
    if mode == "erase":
        run(["sgdisk", "--zap-all", disk])
        run(["sgdisk", "--clear", disk])
        numbers = {}
        for index, part in enumerate(layout, 1):
            numbers[part["role"]] = index
    else:
        used = existing_partition_numbers(disk)
        highest = max(used) if used else 0
        numbers = {}
        for index, part in enumerate(layout, highest + 1):
            numbers[part["role"]] = index
    for part in layout:
        number = numbers[part["role"]]
        run(
            [
                "sgdisk",
                "--new={}:{}:{}".format(number, part["start"], part["end"]),
                "--typecode={}:{}".format(number, part["type"]),
                "--change-name={}:{}".format(number, part["role"]),
                disk,
            ]
        )
    run(["partprobe", disk])
    run(["udevadm", "settle"])
    return numbers


def format_root(device, filesystem):
    if filesystem == "ext4":
        run(["mkfs.ext4", "-F", "-L", "ojuny-root", device])
    elif filesystem == "btrfs":
        run(["mkfs.btrfs", "-f", "-L", "ojuny-root", device])
    elif filesystem == "xfs":
        run(["mkfs.xfs", "-f", "-L", "ojuny-root", device])
    elif filesystem == "f2fs":
        run(["mkfs.f2fs", "-f", "-l", "ojuny-root", device])
    else:
        raise DiskError("unknown filesystem: {}".format(filesystem))


def open_root(device, settings):
    if not settings.encrypt:
        return device
    run(
        ["cryptsetup", "luksFormat", "--type", "luks2", "--batch-mode", "--key-file", "-", device],
        input_text=settings.passphrase,
    )
    run(
        ["cryptsetup", "luksOpen", "--key-file", "-", device, paths.LUKS_NAME],
        input_text=settings.passphrase,
    )
    return "/dev/mapper/" + paths.LUKS_NAME


def format_and_mount(disk, layout, numbers, settings):
    root_part = layout[-1]
    root_device = partition_path(disk, numbers[root_part["role"]])
    esp_device = partition_path(disk, numbers[ROLE_ESP])
    swap_device = (
        partition_path(disk, numbers[ROLE_SWAP]) if ROLE_SWAP in numbers else None
    )

    run(["mkfs.vfat", "-F", "32", "-n", "OJUNY_ESP", esp_device])
    if swap_device:
        run(["mkswap", "-L", "ojuny-swap", swap_device])

    root = open_root(root_device, settings)
    format_root(root, settings.filesystem)

    settings.extras["root_device"] = root_device
    settings.extras["root_mapper"] = root if settings.encrypt else None
    settings.extras["esp_device"] = esp_device
    settings.extras["swap_device"] = swap_device

    os.makedirs(paths.TARGET, exist_ok=True)
    if settings.filesystem == "btrfs":
        run(["mount", root, str(paths.TARGET)])
        for name in ("@", "@home", "@nix"):
            run(["btrfs", "subvolume", "create", os.path.join(str(paths.TARGET), name)])
        run(["umount", str(paths.TARGET)])
        run(["mount", "-o", "subvol=@", root, str(paths.TARGET)])
        os.makedirs(paths.TARGET / "home", exist_ok=True)
        os.makedirs(paths.TARGET / "nix", exist_ok=True)
        run(["mount", "-o", "subvol=@home", root, str(paths.TARGET / "home")])
        run(["mount", "-o", "subvol=@nix", root, str(paths.TARGET / "nix")])
    else:
        run(["mount", root, str(paths.TARGET)])

    os.makedirs(paths.TARGET / "boot", exist_ok=True)
    run(["mount", esp_device, str(paths.TARGET / "boot")])


def unmount():
    subprocess.run(["umount", "-R", str(paths.TARGET)], check=False)


def prepare(settings, reporter):
    region = resolve_free_region(settings) if settings.disk_mode == "free" else None
    if settings.disk_mode == "free" and region is None:
        raise DiskError("no free region of at least 30 GiB on {}".format(settings.disk))
    sector_bytes = sector_size(settings.disk)
    if region:
        start, end = region["start"], region["end"]
    else:
        start = 0
        end = total_sectors(settings.disk) - 34
    layout = plan_layout(
        start,
        end,
        sector_bytes,
        swap_bytes(settings.swap, preflight.memory_bytes()),
    )
    reporter.log(
        "layout: " + ", ".join(
            "{} {}..{}".format(part["role"], part["start"], part["end"]) for part in layout
        )
    )
    numbers = create_partitions(settings.disk, layout, settings.disk_mode)
    format_and_mount(settings.disk, layout, numbers, settings)
    return layout, numbers


def validate_target(settings):
    disk = settings.disk
    if not disk:
        raise DiskError("no target disk selected")
    if not os.path.exists(disk):
        raise DiskError("target disk does not exist: {}".format(disk))
    if not stat.S_ISBLK(os.stat(disk).st_mode):
        raise DiskError("not a block device: {}".format(disk))
    if preflight.is_mounted(disk):
        raise DiskError("refusing to wipe a mounted disk: {}".format(disk))
    size = preflight.resolve_disk_size(disk)
    if size < paths.MIN_DISK_BYTES:
        raise DiskError(
            "target disk is smaller than 30 GiB: {} ({} bytes)".format(disk, size)
        )
    if settings.disk_mode == "free":
        region = resolve_free_region(settings)
        if region is None:
            raise DiskError("no free region of at least 30 GiB on {}".format(disk))
    return True
