# Testing

## Static checks

```sh
nix flake check
```

| Check | What it proves |
| --- | --- |
| `format` | Every Nix file is `nixfmt` clean |
| `python` | Every installer module parses |
| `installer-help` | The `ojuny-install` wrapper starts and imports every module |
| `fixed-paths` | No template-relative path outside `flake_structure.py` |
| `flake-structure` | The vendored contract parser matches the template input |
| `layout-plan` | The sector planner handles both modes, both firmwares, every swap choice and 4k sectors |
| `settings` | Validation and JSON round-trip |
| `iso-size` | The ISO stays under 1.6 GB and prints its size |

## Preflight without installing

```sh
nix run .#install -- --check
```

Prints the model, firmware, memory, CPU count, network state, eligible disks and
every skipped disk with its reason.

## Scripted install in QEMU

```sh
scripts/qemu-test.sh
```

The script builds `packages.ojuny-minimal-iso-test`, creates a 40 GiB qcow2
disk, installs with the fixture settings (bundled template, `/dev/vda`, ext4,
no swap, no encryption, power off), then boots the installed disk with the same
OVMF NVRAM and waits for a login prompt.

Set `ISO=/path/to.iso` to reuse a built image, `INSTALL_TIMEOUT` and
`BOOT_TIMEOUT` to change the limits.

## Attended checklist

1. Build `nixosConfigurations.ojuny-minimal-iso` or `packages.ojuny-minimal-iso`.
2. Boot the ISO on the target machine, preferably over serial with
   `console=ttyS0`.
3. Walk the screens and confirm each value survives to the Summary.
4. Install with erase mode, ext4, no swap, no encryption, reboot.
5. Confirm the installed system reaches a login and the chosen password works.
6. Repeat with LUKS2 root and with BIOS firmware.
7. Install a second template by URL to prove template neutrality.
8. Confirm `~/repos/nix-flake` is a git repository with one commit.
9. Confirm `~/ojuny-install.log` and `~/install-report.json` exist.
