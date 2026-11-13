# Disk layout

The planner is a pure function in `installer/oj_installer/disk.py`, covered by
`checks.layout-plan`. Partitioning uses `sgdisk`, formatting uses the per-
filesystem tools, and mounting goes through `/mnt`.

## Region

- Erase mode: the whole disk, from sector 2048 to the last usable sector
  (total sectors minus the 34 sectors the backup GPT needs).
- Free mode: the largest unallocated region on the target disk that is at least
  30 GiB. It installs alongside existing systems and never resizes them.

## Partitions

| Role | Size | Type | Filesystem |
| --- | --- | --- | --- |
| `bios-boot` | 1 MiB | `EF02` | none |
| `esp` | 4 GiB | `EF00` | vfat, mounted at `/boot` |
| `swap` | none, 4 GiB, or RAM rounded up to GiB | `8200` | swap |
| `root` | remainder, at least 20 GiB | `8300` | ext4, btrfs, xfs or f2fs |

Every partition starts and ends on a 2048-sector boundary. The layout is
checked against the region before anything is written, so a region that can
not hold the fixed partitions plus a 20 GiB root stops with an error instead of
a half-written disk.

## Filesystems

- ext4: `mkfs.ext4 -F`
- btrfs: `mkfs.btrfs -f`, then `@`, `@home` and `@nix` subvolumes mounted at
  `/`, `/home` and `/nix`
- xfs: `mkfs.xfs -f`
- f2fs: `mkfs.f2fs -f`

LUKS2 wraps the root partition only. The mapper is always `cryptroot`; the
passphrase is passed on standard input, never on the command line.

## Mount order

1. root device (or `/dev/mapper/cryptroot`) at `/mnt`
2. `@home` and `@nix` for btrfs
3. the ESP at `/mnt/boot`

`nixos-generate-config` then sees exactly the layout that the hardware module
records.
