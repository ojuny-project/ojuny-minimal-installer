# DRAFT - ojuny-minimal-installer

Status: implemented 2026-11-12. The ISO builds, `nix flake check` passes and the
engine is covered by the layout and settings checks. No hardware install has
been completed; the QEMU install run is written but not part of the build.

## Purpose

The reference terminal installer for Ojuny templates. It installs any template
that can be installed, booted and run, from a console-only live ISO with no
desktop environment and no Calamares.

It is the companion to `ojuny-minimal-template`, which states that the installer
implementation lives here, and the terminal counterpart of `ojuny-installer`,
which is the Calamares and offline path.

## Position in the project

| Repository | Role |
| --- | --- |
| `ojuny-template` | Full desktop template. Defines the module contract. |
| `ojuny-minimal-template` | Smallest valid template. The bundled install source. |
| `ojuny-installer` | Calamares installer with discovery and offline variants. |
| `ojuny-minimal-installer` | This repository. TTY installer, one online ISO. |

This repository does not fork the template and does not duplicate its install
logic into the template.

## What the repository contains

```text
ojuny-minimal-installer/
  flake.nix                   ISO, installer app, checks, dev shell
  nixos/
    iso.nix                   minimal live ISO and the tty1 service
    common.nix                live packages, /etc/ojuny paths, template source
    eject.nix                 remove-the-medium prompt
    test.nix                  scripted test fixture, not a product variant
  installer/
    default.nix               the ojuny-install package
    oj_installer/
      main.py                 entry point and screen state machine
      tui.py                  curses primitives
      screens.py              welcome, template, origin, system, disk, summary
      preflight.py            machine and disk discovery
      settings.py             the settings record and validation
      disk.py                 layout planner, partitioning, mounting
      hardware.py             hardware, facter, LUKS lines, bootloader
      template.py             acquire, inject, git
      install.py              the seven engine phases
      postinstall.py          flake copy, ownership, log, report
      paths.py                every fixed path and constant
      flake_structure.py      byte-identical copy of the template parser
  docs/                       screen flow, engine, disk layout, limits, testing
  tests/                      layout, settings and fixed-path checks
  scripts/qemu-test.sh        install and boot check in QEMU
```

### Flake outputs

- `packages.ojuny-minimal-iso`: the live ISO.
- `packages.ojuny-minimal-iso-test`: the scripted fixture ISO for the QEMU test.
- `packages.ojuny-install`, `apps.install`: the installer for an existing NixOS.
- `apps.ci`, `devShells.default`, `checks.*`.
- `nixosConfigurations.ojuny-minimal-iso`.

### Install engine

Seven phases: check the target, prepare the template, partition and format,
generate hardware, `nixos-install`, finish the configuration, unmount. Details
are in `docs/install-engine.md`. The template is acquired before the disk is
written, so a bad URL fails without destroying data.

### Terminal interface

Full-screen TUI in the tty. Standard library curses, no Qt, no Wayland, no
extra toolkit. Nine screens, keyboard only. Details are in
`docs/screen-flow.md`.

### Documentation

- The screen flow and key map.
- The engine phases and the template module contract.
- The sector layout and filesystem handling.
- The limits, including what the minimal installer deliberately does not do.
- The static checks and the QEMU procedure.

## Decisions

1. Engine and TUI are Python 3 with the standard library only.
2. The ISO base is `installation-cd-minimal.nix`; the desktop, Calamares, Qt,
   plymouth and the debug SSH probe are not imported.
3. Disks are planned on sectors: whole-disk erase or the largest free region of
   at least 30 GiB. The installer never shrinks a filesystem.
4. Templates are either bundled (the ISO's `ojuny-minimal-template` input, the
   default) or prepared (a git URL with an optional token and branch).
5. Template helpers (`prepare-repo`, `regenerate-hardware`, `ojuny-bootorder`)
   are used when the bundled input provides them. The generic path always
   exists, because `ojuny-minimal-template` ships none of them.
6. There is no persistent image, unattended product variant, discovery cache or
   offline closure.

## Limits and non-goals

See `docs/limits.md` for the full list. The short version: `x86_64-linux`,
online only, erase or free space, LUKS2 root only, no secure boot, no Wi-Fi.

## Open questions

- Is a swap-with-hibernate option worth the resume wiring?
- Should the installer offer to keep an existing ESP instead of always creating
  a 4 GiB one?
- Should prepared installs be able to inject the account from the System screen
  instead of keeping the repository's own user?

## Sources

- `ojuny-template/docs/12-flake-module-contract.md`, `03-host-setup.md`.
- `ojuny-minimal-template/DRAFT.md`, `README.md`.
- `ojuny-installer/README.md`, `docs/attended-install.md`,
  `docs/unattended-install.md`, `nixos/unattended-install.py`,
  `packages/ojuny-calamares-extensions/modules/ojuny/main.py`.
