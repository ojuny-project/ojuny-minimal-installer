{
  lib,
  pkgs,
  ...
}:

{
  systemd.services.ojuny-live-media-eject = {
    description = "Prompt to remove the installation medium";
    wantedBy = [ "final.target" ];
    after = [
      "shutdown.target"
      "umount.target"
    ];
    before = [ "final.target" ];
    unitConfig.DefaultDependencies = false;
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      TimeoutStartSec = "infinity";
      ExecStart = pkgs.writeShellScript "ojuny-live-media-eject" ''
        exec </dev/console >/dev/console 2>&1
        ${lib.getExe' pkgs.coreutils "stty"} sane 2>/dev/null || true
        printf '\nPlease remove the installation medium, then press ENTER.\n'
        read -r _ || true
      '';
    };
  };
}
