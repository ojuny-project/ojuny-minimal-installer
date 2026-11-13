{
  writeShellApplication,
  python3,
  ncurses,
  btrfs-progs,
  cryptsetup,
  curl,
  dosfstools,
  e2fsprogs,
  efibootmgr,
  f2fs-tools,
  gptfdisk,
  git,
  lib,
  mkpasswd,
  nix,
  nixos-facter,
  nixos-install-tools,
  openssh,
  parted,
  util-linux,
  xfsprogs,
}:

writeShellApplication {
  name = "ojuny-install";

  runtimeInputs = [
    btrfs-progs
    cryptsetup
    curl
    dosfstools
    e2fsprogs
    efibootmgr
    f2fs-tools
    gptfdisk
    git
    mkpasswd
    nix
    nixos-facter
    nixos-install-tools
    openssh
    parted
    python3
    util-linux
    xfsprogs
  ];

  text = ''
    export PYTHONPATH=${./.}''${PYTHONPATH:+:$PYTHONPATH}
    export TERMINFO_DIRS=${ncurses}/share/terminfo''${TERMINFO_DIRS:+:$TERMINFO_DIRS}
    exec ${lib.getExe python3} -m oj_installer "$@"
  '';
}
