# DRAFT - ojuny-minimal-installer

Status: draft scope. Nothing is built. This file describes what the repository
is supposed to contain, not what it contains today.

## Purpose

The reference terminal installer for Ojuny templates. It installs any template
that can be installed, booted and run, and it is the base that the Pro, Console
and Home Server installers extend.

It replaces the graphical installer path with a terminal interface. The install
engine is shared and scriptable so the same code can run attended, unattended,
offline and from a discovery cache.

## Position in the project

`ojuny-installer` is the Calamares path for the full desktop template. This
repository is the terminal path and the reference implementation of "install
an arbitrary Ojuny template". The other installers may reuse its engine or its
image definitions, but they do not fork the install logic.

## What the repository will contain

```text
ojuny-minimal-installer/
  flake.nix                 ISO and app outputs
  nixos/                    live ISO profiles
    installer.nix           base live system
    offline.nix             full-system closure
    discovery.nix           nix-cache-discovery profile
    unattended.nix          automatic install
  installer/                terminal UI and install engine
    preflight/              requirements and target checks
    disk/                   partitioning, LUKS, mount layout
    template/               fetch, validate and inject a template
    system/                 users, hostname, network, bootloader
    report/                 progress and error handling
  docs/                     screen flow, unattended schema, tests
  tests/                    VM and hardware checklists
```

### Flake outputs

- `packages.ojuny-iso`: attended online ISO.
- `packages.ojuny-iso-offline`: attended offline ISO.
- `packages.ojuny-iso-discovery`: attended discovery ISO.
- `packages.unattended-iso`, `unattended-iso-offline`,
  `unattended-iso-discovery`.
- `apps.install`: run the terminal installer from an existing NixOS system.
- `apps.make-iso`: build an ISO for a chosen template and variant.
- `apps.make-unattended-iso`: build an unattended ISO with a config file.
- `checks.*`: VM boot and install checks.

### Install engine

- Preflight: architecture, RAM, disk size, network, UEFI or BIOS, Nix features.
- Template selection: git URL, flake reference or local path; the repository is
  cloned or copied to the target.
- Template validation: the flake has a `nixosConfigurations` output, the setup
  generators can run, the target builds, and the installed system boots.
- Injection: write the hardware module, the user module and the host
  registration. Never edit the template's hand-written pages.
- Disk layout: manual selection or disko-driven automatic layout, optional
  LUKS2 root, swap policy, ESP or XBOOTLDR handling.
- System install: `nixos-install --flake`, bootloader, first-boot wiring.
- Completion: print the installed path and the next command, then offer reboot.

### Terminal interface

- Full-screen TUI with keyboard navigation and no graphical dependencies.
- Screens for template, disk, encryption, user, hostname, network, summary and
  progress.
- A non-interactive mode driven by a config file for unattended installs.
- A readable log and a final summary that can be copied for support.
- Controller or serial operation for headless machines.

### Image variants

- Attended online: fetch the template and build on the target.
- Attended offline: carry the template closure and locked inputs.
- Attended discovery: use `nix-cache-discovery` peers on the local network.
- Unattended versions of all three, with the same destructive disk policy.

### Documentation

- The TUI screen flow and key map.
- The unattended config schema and defaults.
- What makes a template installable and bootable, and how the installer checks
  it.
- Disk layouts, firmware handling and encryption limits.
- How to add a product variant without forking the engine.

### Tests

- Boot each ISO in QEMU and reach the first screen.
- Install `ojuny-minimal-template` and boot the installed system.
- Install a second template with a different desktop to prove neutrality.
- Install offline with the network disabled.
- Reject a template that cannot be installed or does not boot.
- Verify that an existing disk is never overwritten without confirmation.

## Limits and non-goals

- `x86_64-linux` only.
- Destructive unattended installs. The target disk is wiped by design.
- No Wi-Fi configuration in the unattended path.
- No NTFS resizing. Windows must be prepared before install.
- No Secure Boot key enrollment. It remains a post-install step.
- No product-specific defaults. Those live in the product installers.
- No graphical installer. That remains `ojuny-installer`.

## Open questions

- Is the engine a shell library, a Rust binary, or a Nix-generated script?
- Which terminal UI library is acceptable on the live image?
- Does the minimal installer need the persistent USB image path, or is that
  only in the full installer?
- Should an installability check be a hard failure or a warning?

## Sources

- `ojuny-installer/README.md` and `docs/unattended-install.md`,
  `docs/offline-install.md`, `docs/remote-deployment.md`,
  `docs/persistent-image.md`.
- `ojuny-template/docs/03-host-setup.md`.
- `nixos-configs/notes/Ojuny Deployment Methods.md`.
