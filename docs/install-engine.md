# Install engine

`installer/oj_installer/install.py` runs seven phases. Each phase writes a
timestamped line to `/tmp/ojuny-install.log`, which is copied to
`~/ojuny-install.log` in the installed system.

## Phases

1. Checking the target. `disk.validate_target` refuses a missing, mounted,
   non-block or sub-30-GiB target, and `wait_for_network` retries the cache
   endpoint for two minutes.
2. Preparing the template. The clone or copy happens before anything is
   written to the target, so a bad URL or token fails without wiping a disk.
   - Bundled: copy `/etc/ojuny/flake`, which is the `ojuny-minimal-template`
     input of this flake. If the input exposes a `prepare-repo` package, the
     engine runs it with the account, hostname, locale, keymap, timezone and
     state version. Otherwise it injects the generated modules itself.
   - Prepared: `git clone` the URL, with `--branch` when given and an
     in-memory credential file when a token is given. The clone keeps its own
     user and configuration modules.
3. Partitioning and formatting. See `docs/disk-layout.md`.
4. Generating hardware. `nixos-generate-config --root /mnt`, or the input's
   `regenerate-hardware` when bundled and available. The result is written as
   the `system-hardware` and `system-bootloader` modules, LUKS device lines are
   keyed by the encrypted parent UUID, the facter report is written, and the
   host imports module is updated.
5. Installing NixOS. `nixos-install --no-root-passwd --root /mnt --flake
   <staging>#<host>` streamed line by line. The progress screen counts
   completed phases and displays store activity.
6. Finishing the configuration. The staging tree is copied to
   `/mnt/home/<user>/repos/nix-flake`; it was already committed to git before
   `nixos-install`, so the copy keeps that history. The optional origin and
   credential helper are set, the settings GUI config is written, the home tree
   is handed to the user, and the log and report are copied.
7. Unmounting and syncing.

On UEFI the engine snapshots `efibootmgr` before `nixos-install`, restores the
recorded `BootOrder` afterwards, then moves `Linux Boot Manager` above the
first internal entry. On BIOS it does nothing.

## Template contract

Every template write goes through `flake_structure`:

| Content | Module | Fallback |
| --- | --- | --- |
| System settings | `flake.modules.nixos.system-configuration` | `modules/00-configuration.nix` |
| User account | `flake.modules.nixos.users` | `modules/00-user.nix` |
| Host registration | `flake.nixosConfigurations.<host>` | `modules/00-host.nix` |
| Hardware | `flake.modules.nixos.system-hardware` | `modules/00-hardware.nix` |
| Bootloader | `flake.modules.nixos.system-bootloader` | same hardware file |
| Host imports | `flake.modules.nixos.host-imports` | `modules/00-imports.nix` |
| Facter report | none | `modules/facter.json` |

`installer/oj_installer/flake_structure.py` is a byte-identical copy of
`ojuny-template/scripts/flake_structure.py`. `checks.flake-structure` compares
it with the bundled template input.

The generated users module carries the `@menu` / `@option` header the settings
GUI expects. The generated hardware module has no such header and never appears
as a settings page.

## Generated bootloader rules

- UEFI: systemd-boot, `canTouchEfiVariables`, ESP mounted at `/boot`.
- BIOS: GRUB on the target disk with `useOSProber`; a btrfs root also sets
  `fsIdentifier = "provided"`.
- BIOS with LUKS2 root: `/boot/crypto_keyfile.bin` is written (512 bytes, mode
  0600), `boot.initrd.secrets`, `boot.loader.grub.enableCryptodisk` and a
  key-file line per mapper are added, and the keyslot is converted to PBKDF2 so
  GRUB can open it.
- Another internal ESP present: `flake_structure.ensure_multiboot` is called.
  A template without a multiboot module logs a warning and continues.
