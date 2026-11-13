"""What happens after nixos-install: the installed flake, ownership, log, report."""

import json
import os
import shutil
import subprocess
import time

from . import paths, template


def lookup_ids(username):
    with open(paths.TARGET_PASSWD, encoding="utf-8") as handle:
        for line in handle:
            fields = line.strip().split(":")
            if len(fields) >= 4 and fields[0] == username:
                return int(fields[2]), int(fields[3])
    raise RuntimeError("user not found in the installed system: {}".format(username))


def chown_tree(path, uid, gid):
    os.lchown(path, uid, gid)
    for current, directories, files in os.walk(path, followlinks=False):
        for name in directories + files:
            os.lchown(os.path.join(current, name), uid, gid)


def write_gui_config(home, clone, host, shell):
    config_dir = os.path.join(home, ".config", "nix-settings-gui")
    os.makedirs(config_dir, exist_ok=True)
    payload = {
        "flake_path": clone,
        "terminal_command": "ghostty -e {} -c".format(shell),
        "rebuild_command": (
            'sudo echo "starting rebuild"; sudo nixos-rebuild switch --flake {}#{} '
            '|& nom; echo "finished build, press any button to close the window"; '
            "read -n 1"
        ).format(clone, host),
        "reload_dms_on_rebuild": True,
    }
    with open(os.path.join(config_dir, "config.json"), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def write_report(engine, staging, host, clone):
    settings = engine.settings
    try:
        flake_revision = template.output(["git", "-C", str(clone), "rev-parse", "HEAD"])
    except template.TemplateError:
        flake_revision = None
    report = {
        "installer": "ojuny-minimal-installer",
        "installer_version": "0.1.0",
        "template": template.template_repository(),
        "template_revision": template.template_revision(),
        "mode": settings.mode,
        "host": host,
        "username": settings.username,
        "disk": settings.disk,
        "disk_mode": settings.disk_mode,
        "filesystem": settings.filesystem,
        "swap": settings.swap,
        "encryption": "luks2" if settings.encrypt else None,
        "firmware": settings.firmware,
        "flake_revision": flake_revision,
        "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(paths.INSTALL_REPORT, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")


def copy_logs_and_report(home, uid, gid):
    for source, name, mode in (
        (paths.INSTALL_LOG, "ojuny-install.log", 0o644),
        (paths.INSTALL_REPORT, "install-report.json", 0o644),
    ):
        if not source.exists():
            continue
        target = os.path.join(home, name)
        shutil.copyfile(source, target)
        os.chmod(target, mode)
        os.chown(target, uid, gid)


def finish(engine, staging, host):
    settings = engine.settings
    home = str(paths.TARGET / "home" / settings.username)
    os.makedirs(home, exist_ok=True)

    engine.log("copying the configuration to {}".format(home))
    clone = template.copy_to_home(staging, home, settings.clone_relative)
    template.setup_origin(clone, settings, home, settings.username)

    shell = template.detect_shell(clone)
    write_gui_config(home, "/home/{}/{}".format(settings.username, settings.clone_relative), host, shell)
    write_report(engine, staging, host, clone)

    uid, gid = lookup_ids(settings.username)
    engine.log("handing the home directory to {}:{}".format(uid, gid))
    chown_tree(home, uid, gid)
    copy_logs_and_report(home, uid, gid)

    shutil.rmtree(staging, ignore_errors=True)
    subprocess.run(["sync"], check=False)
