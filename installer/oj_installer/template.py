"""Template acquisition, preparation, injection and git setup.

Nothing in this module knows a template path. Every write goes through
flake_structure and the flake module contract.
"""

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from . import flake_structure, paths


class TemplateError(Exception):
    pass


def run(command, input_text=None, check=True):
    result = subprocess.run(
        command,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if check and result.returncode != 0:
        raise TemplateError(
            "command failed ({}): {}\n{}{}".format(
                result.returncode,
                " ".join(str(part) for part in command),
                result.stdout,
                result.stderr,
            )
        )
    return result


def output(command):
    return run(command).stdout.strip()


def nix_string(value):
    return json.dumps(str(value), ensure_ascii=False)


def helpers():
    """Helper commands provided by the bundled template, if any."""
    try:
        payload = json.loads(paths.LIVE_HELPERS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    return {name: payload.get(name) or None for name in ("prepareRepo", "regenerateHardware", "bootorder")}


def template_revision():
    try:
        return paths.LIVE_TEMPLATE_REVISION.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


def state_version():
    try:
        with open("/etc/os-release", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VERSION_ID="):
                    match = re.match(r"(\d+\.\d+)", line.split("=", 1)[1].strip().strip('"'))
                    if match:
                        return match.group(1)
    except OSError:
        pass
    for command in ("/run/current-system/sw/bin/nixos-version", "nixos-version"):
        try:
            text = subprocess.check_output([command], text=True).strip()
        except OSError:
            continue
        match = re.match(r"(\d+\.\d+)", text)
        if match:
            return match.group(1)
    raise TemplateError("could not determine the NixOS release")


def clean_flake(root, keep_git=False):
    names = (".direnv", "result", "result-1") if keep_git else (".git", ".direnv", "result", "result-1")
    for name in names:
        target = Path(root) / name
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)


def clone_prepared(url, token, branch, destination):
    args = ["git", "clone"]
    if branch:
        args += ["--branch", branch]
    args += [url, destination]
    if token and url.startswith(("http://", "https://")):
        from urllib.parse import quote, urlparse

        parsed = urlparse(url)
        if not parsed.hostname:
            raise TemplateError("invalid repository URL: {}".format(url))
        user = parsed.username or "x-access-token"
        directory = tempfile.mkdtemp(prefix="ojuny-git-")
        try:
            os.chmod(directory, 0o700)
            credentials = os.path.join(directory, "credentials")
            with open(credentials, "w", encoding="utf-8") as handle:
                handle.write(
                    "https://{}:{}@{}\n".format(user, quote(token, safe=""), parsed.hostname)
                )
            os.chmod(credentials, 0o600)
            run([args[0], "-c", "credential.helper=store --file={}".format(credentials)] + args[1:])
        finally:
            shutil.rmtree(directory, ignore_errors=True)
    else:
        run(args)


def acquire(settings, reporter):
    """Copy or clone the template into a staging directory."""
    staging = tempfile.mkdtemp(prefix=paths.STAGING_PREFIX)
    if settings.mode == "prepared":
        reporter.log("cloning {}".format(settings.template_url))
        try:
            clone_prepared(
                settings.template_url,
                settings.template_token,
                settings.template_branch,
                staging,
            )
        except TemplateError as error:
            raise TemplateError(
                "could not clone the prepared template repository {}: {}\n"
                "The install stopped. Correct the URL, token or branch and retry.".format(
                    settings.template_url, error
                )
            ) from error
        clean_flake(staging, keep_git=True)
    else:
        reporter.log("copying the bundled template from {}".format(paths.LIVE_TEMPLATE))
        if not paths.LIVE_TEMPLATE.is_dir():
            raise TemplateError("the live template source is missing: {}".format(paths.LIVE_TEMPLATE))
        shutil.copytree(str(paths.LIVE_TEMPLATE), staging, symlinks=True, dirs_exist_ok=True)
        run(["chmod", "-R", "u+w", staging])
        clean_flake(staging)
    return staging


def preferred_host(staging):
    host = flake_structure.preferred_host(staging)
    if not host:
        raise TemplateError(
            "the template has no nixosConfigurations host. A template must declare "
            "one; see ojuny-template/docs/12-flake-module-contract.md."
        )
    return host


def detect_username(staging):
    found = flake_structure.find_modules(staging, "users")
    if not found:
        return None
    text = Path(found[0]).read_text(encoding="utf-8")
    match = re.search(
        r'users\.users\s*=\s*\{\s*(?:"([^"]+)"|([A-Za-z0-9_][A-Za-z0-9_-]*))\s*=',
        text,
    )
    if not match:
        return None
    return match.group(1) or match.group(2)


def detect_shell(staging):
    found = flake_structure.find_modules(staging, "users")
    if not found:
        return "zsh"
    text = Path(found[0]).read_text(encoding="utf-8")
    match = re.search(r'shell\s*=\s*pkgs\.([A-Za-z0-9_-]+)\s*;', text)
    return match.group(1) if match else "zsh"


def uses_home_manager(staging):
    try:
        return "home-manager" in (Path(staging) / "flake.nix").read_text(encoding="utf-8")
    except OSError:
        return False


def user_module(username, fullname, hashed_password, shell, version, home_manager):
    home_import = (
        " inputs.home-manager.nixosModules.home-manager" if home_manager else ""
    )
    home_option = " homeManager = true;" if home_manager else ""
    home_block = (
        """
      home-manager.users = {{
        {username} = {{
          home.stateVersion = "{version}";
        }};
      }};""".format(username=username, version=version)
        if home_manager
        else ""
    )
    return """/* @menu
   displayname = "Users";
   icon = "avatar-default-symbolic";
   order = 10;
   description = "User Accounts";
   category = "01-Users";
*/

{{ self, inputs, ... }}: {{

  flake.modules.nixos.users = {{ pkgs, ... }}: {{

    imports = [{home_import} ];

    config = {{
      /* @option widget = "users"; label = "Accounts";{home_option} */
      users.users = {{
        {username} = {{
          isNormalUser = true;
          uid = 1000;
          description = {fullname};
          extraGroups = [ "networkmanager" "wheel" "video" "input" ];
          hashedPassword = {hashed_password};
          openssh.authorizedKeys.keys = [ ];
          shell = pkgs.{shell};
        }};
      }};
{home_block}
    }};

  }};

}}
""".format(
        username=username,
        fullname=nix_string(fullname),
        hashed_password=nix_string(hashed_password),
        shell=shell,
        version=version,
        home_import=home_import,
        home_option=home_option,
        home_block=home_block,
    )


def inject(staging, settings, runtime_clone, version, hashed_password):
    """Write the generated modules the contract defines."""
    flake_structure.ensure_configuration(
        staging,
        {
            "hostname": settings.hostname,
            "state_version": version,
            "timezone": settings.timezone,
            "locale": settings.locale,
            "keymap": settings.keymap,
            "repo_path": runtime_clone,
        },
        interactive=False,
        fallback_rel="modules/00-configuration.nix",
    )
    flake_structure.ensure_users(
        staging,
        user_module(
            settings.username,
            settings.fullname or settings.username,
            hashed_password,
            settings.shell,
            version,
            uses_home_manager(staging),
        ),
        interactive=False,
        fallback_rel="modules/00-user.nix",
    )
    flake_structure.ensure_host(
        staging,
        settings.hostname,
        runtime_clone,
        interactive=False,
        fallback_rel="modules/00-host.nix",
    )


def ensure_imports(staging):
    imports = [
        name
        for name in (
            "system-configuration",
            "users",
            "system-hardware",
            "system-bootloader",
            "system-hardware-quirks",
        )
        if flake_structure.find_modules(staging, name)
    ]
    flake_structure.ensure_imports(
        staging, imports, interactive=False, fallback_rel="modules/00-imports.nix"
    )
    return imports


def run_helper(path, arguments):
    return run([path] + arguments)


def prepare_bundled(staging, settings, runtime_clone, version, hashed_password, reporter):
    helper = helpers()["prepareRepo"]
    if not helper:
        return False
    reporter.log("running the bundled prepare-repo helper")
    run_helper(
        helper,
        [
            "--root",
            staging,
            "--template",
            str(paths.LIVE_TEMPLATE),
            "--username",
            settings.username,
            "--fullname",
            settings.fullname or settings.username,
            "--hashed-password",
            hashed_password,
            "--shell",
            settings.shell,
            "--hostname",
            settings.hostname,
            "--state-version",
            version,
            "--clone-relative",
            settings.clone_relative,
            "--timezone",
            settings.timezone,
            "--locale",
            settings.locale,
            "--keymap",
            settings.keymap,
            "--force",
            "--non-interactive",
        ],
    )
    return True


def git_init(root, message="Initial Ojuny configuration"):
    run(["git", "-C", root, "init", "-q"])
    run(["git", "-C", root, "add", "-A"])
    run(
        [
            "git",
            "-C",
            root,
            "-c",
            "user.name=Ojuny Installer",
            "-c",
            "user.email=installer@ojuny.local",
            "commit",
            "-qm",
            message,
            "--allow-empty",
        ]
    )


def copy_to_home(staging, home, clone_relative):
    clone = Path(home) / clone_relative
    if clone.exists():
        shutil.rmtree(clone)
    clone.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(staging, clone, symlinks=True)
    return clone


def write_credentials(home, url, token):
    from urllib.parse import quote, urlparse

    parsed = urlparse(url)
    credentials = Path(home) / ".git-credentials"
    credentials.parent.mkdir(parents=True, exist_ok=True)
    credentials.write_text(
        "https://{}:{}@{}\n".format(
            parsed.username or "x-access-token",
            quote(token, safe=""),
            parsed.hostname,
        ),
        encoding="utf-8",
    )
    os.chmod(credentials, stat.S_IRUSR | stat.S_IWUSR)


def set_credential_helper(clone, username):
    run(
        [
            "git",
            "-C",
            str(clone),
            "config",
            "credential.helper",
            "store --file=/home/{}/.git-credentials".format(username),
        ]
    )


def setup_origin(clone, settings, home, username):
    """Prepared installs keep the template origin; bundled installs may set one."""
    if settings.mode == "prepared":
        if settings.template_token and settings.template_url.startswith(("http://", "https://")):
            write_credentials(home, settings.template_url, settings.template_token)
            set_credential_helper(clone, username)
        return
    if not settings.origin_url:
        return
    run(["git", "-C", str(clone), "remote", "remove", "origin"], check=False)
    run(["git", "-C", str(clone), "remote", "add", "origin", settings.origin_url])
    if settings.origin_token and settings.origin_url.startswith(("http://", "https://")):
        write_credentials(home, settings.origin_url, settings.origin_token)
        set_credential_helper(clone, username)
