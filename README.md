# ojuny-minimal-installer

The reference terminal installer for Ojuny templates. It boots a console-only
NixOS live ISO, installs any template that follows the Ojuny module contract,
and leaves an installed system that boots and runs.

It is the companion to
[ojuny-minimal-template](https://github.com/ojuny-project/ojuny-minimal-template)
and the terminal counterpart of
[ojuny-installer](https://github.com/ojuny-project/ojuny-installer), which is
the Calamares path. This repository has one online ISO, no desktop
environment, no discovery variant and no offline variant.

> Status: the ISO builds at 1.39 GiB, `nix flake check` passes and the engine is
> covered by the layout and settings checks. No hardware install has been
> completed. Applies to commit at the time of writing, 2026-11-12.

## Requirements

- `x86_64-linux` with Nix and flakes enabled.
- 3.5 GB RAM, a 30 GB target disk and a wired network.
- An 8 GB USB key for the ISO.

## Build

```sh
nix build .#ojuny-minimal-iso     # the live ISO
nix run .#install                 # the installer on an existing NixOS system
nix develop                       # python3, qemu, OVMF, formatters
```

Images land in `result/iso/*.iso`.

## Install

Boot the ISO. The installer starts on the console; use `console=ttyS0` on a
headless machine. With no repository URL it installs the
`ojuny-minimal-template` that is embedded in the ISO. Enter a repository URL to
install a fork instead.

The screens are Welcome, Template, Git origin, System, Disk, Summary, Progress
and Finished. See [docs/screen-flow.md](docs/screen-flow.md) for the key map
and every field.

The installed configuration is written to `/home/<user>/repos/nix-flake`,
committed to git, with an optional origin. `~/ojuny-install.log` and
`~/install-report.json` are copied into the installed system.

## What the installer writes

Only the generated modules the contract defines: system configuration, users,
host registration, hardware, bootloader, host imports and the facter report.
Hand-written template pages are never edited. See
[docs/install-engine.md](docs/install-engine.md).

## Limits

`x86_64-linux` only, online only, erase or free-space installs, no NTFS resize,
no filesystem shrink, LUKS2 root only, no swap encryption, no secure boot
enrollment, no Wi-Fi. Read [docs/limits.md](docs/limits.md) before reporting a
missing feature.

## Documentation

- [Screen flow](docs/screen-flow.md)
- [Install engine](docs/install-engine.md)
- [Disk layout](docs/disk-layout.md)
- [Limits](docs/limits.md)
- [Testing](docs/testing.md)
- [Scope](DRAFT.md)

## Contributing

Report issues on GitHub. A patch includes the change, a passing
`nix flake check`, and a matching documentation update.

## License

GPL-3.0. See [LICENSE](LICENSE).
