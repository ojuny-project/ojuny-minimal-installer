{
  lib,
  pkgs,
  modulesPath,
  ...
}:

let
  installer = pkgs.callPackage ../installer { };
in
{
  imports = [
    (modulesPath + "/installer/cd-dvd/installation-cd-minimal.nix")
    ./common.nix
    ./eject.nix
  ];

  isoImage.edition = lib.mkForce "minimal";
  isoImage.volumeID = lib.mkForce "OJUNY_MINIMAL";
  isoImage.makeBiosBootable = true;
  image.baseName = lib.mkForce "ojuny-minimal-installer";

  services.getty.autologinUser = lib.mkForce null;

  # The installer owns the boot console. Automatic getties would flush its
  # output and fight it for standard input. Leaving the installer starts a
  # shell on the same console.
  boot.kernelParams = [ "systemd.getty_auto=0" ];

  systemd.services.ojuny-minimal-install = {
    description = "Ojuny minimal TTY installer";
    wantedBy = [ "multi-user.target" ];
    after = [ "local-fs.target" ];
    conflicts = [ "getty@tty1.service" ];
    environment.TERM = "linux";
    serviceConfig = {
      Type = "oneshot";
      TTYPath = "/dev/console";
      StandardInput = "tty-force";
      StandardOutput = "tty";
      StandardError = "tty";
      ExecStart = "${installer}/bin/ojuny-install";
      TimeoutStartSec = "0";
      RemainAfterExit = true;
    };
  };
}
