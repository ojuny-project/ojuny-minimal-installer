{
  lib,
  pkgs,
  ...
}:

let
  installer = pkgs.callPackage ../installer { };

  settings = {
    mode = "bundled";
    locale = "en_US.UTF-8";
    keymap = "us";
    timezone = "UTC";
    hostname = "ojuny";
    username = "user";
    fullname = "Test User";
    password = "ojuny-test";
    shell = "zsh";
    firmware = "efi";
    disk = "/dev/vda";
    disk_mode = "erase";
    filesystem = "ext4";
    swap = "none";
    encrypt = false;
    serial_console = true;
    clone_relative = "repos/nix-flake";
    final_action = "poweroff";
  };
in
{
  # Test fixture: an ISO that installs without screens. It is not a product
  # variant; scripts/qemu-test.sh builds it to prove the engine works.
  environment.etc."ojuny/settings.json".text = builtins.toJSON settings;

  boot.kernelParams = lib.mkForce [
    "console=ttyS0"
    "systemd.getty_auto=0"
  ];

  image.baseName = lib.mkOverride 60 "ojuny-minimal-installer-test";

  systemd.services.ojuny-minimal-install.serviceConfig.ExecStart = lib.mkForce (
    "${installer}/bin/ojuny-install --settings /etc/ojuny/settings.json --yes"
  );
}
