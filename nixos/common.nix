{
  lib,
  pkgs,
  inputs,
  ...
}:

let
  template = inputs.ojuny-minimal-template;
  tools = template.packages.${pkgs.stdenv.hostPlatform.system} or { };
  templateRevision = template.rev or template.dirtyRev or "unknown";

  helpers = builtins.toJSON {
    prepareRepo = tools.prepare-repo or null;
    regenerateHardware = tools.regenerate-hardware or null;
    bootorder = tools.ojuny-bootorder or null;
  };
in
{
  nix.settings.experimental-features = [
    "nix-command"
    "flakes"
  ];

  environment.etc."ojuny/flake".source = template.outPath;
  environment.etc."ojuny/template-revision".text = templateRevision;
  environment.etc."ojuny/helpers.json".text = helpers;

  environment.systemPackages = [
    (pkgs.callPackage ../installer { })
    pkgs.git
    pkgs.nixos-facter
  ];

  system.nixos.distroName = "Ojuny";
  system.nixos.distroId = "ojuny";

  documentation.enable = lib.mkForce false;
  documentation.nixos.enable = lib.mkForce false;
  services.openssh.enable = lib.mkForce false;

  boot.kernelParams = [ "console=tty0" ];
}
