# Limits

- `x86_64-linux` only.
- One online ISO. The installer needs network access for `nixos-install`.
  There is no offline closure, no discovery cache, no persistent image and no
  unattended product variant. `nixos/test.nix` is a test fixture, not a
  supported image.
- Erase-disk and free-space installs only. The installer never shrinks a
  filesystem and never resizes NTFS. Shrink a Windows partition in Windows Disk
  Management before installing alongside it.
- The installer always creates its own 4 GiB ESP. It never reuses a Windows ESP
  and never writes an entry next to `EFI/Microsoft`.
- LUKS2 encrypts the root partition only. Swap is not encrypted and hibernate
  is not wired, so `swap = suspend` gives a swap partition without resume.
- BIOS with encrypted root writes a key file to the unencrypted ESP so GRUB can
  open the root device without a typed passphrase. This matches the reference
  attended installer.
- No LVM, no RAID, no ZFS, no secure boot key enrollment, no Wi-Fi
  configuration.
- No nixos-hardware profile detection. A template that ships
  `system-hardware-quirks` keeps whatever it ships; the installer does not
  write one.
- Prepared installs keep the repository's own user, hostname and
  configuration. The account values on the System screen apply to bundled
  installs.
- Progress is phase based plus a count of store activity lines. It is not the
  item-completion counter of the Calamares installer.
- Serial operation follows `/dev/console`. Boot the ISO with `console=ttyS0` on
  a headless machine. The live image disables automatic getties
  (`systemd.getty_auto=0`), so the installer owns the console; leaving it starts
  a shell there. The `Serial console` option adds `console=tty0 console=ttyS0`
  to the installed system, which starts a getty on ttyS0.
