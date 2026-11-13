"""The one settings record shared by the TUI, the engine and scripted runs."""

import json
import re
from dataclasses import asdict, dataclass, field, fields

from . import paths

FILESYSTEMS = ("ext4", "btrfs", "xfs", "f2fs")
SWAP_CHOICES = ("none", "small", "suspend")
DISK_MODES = ("erase", "free")
FIRMWARE_CHOICES = ("efi", "bios")
TEMPLATE_MODES = ("bundled", "prepared")
FINAL_ACTIONS = ("reboot", "poweroff")

USERNAME_RE = re.compile(r"[a-z_][a-z0-9_-]*")
HOSTNAME_RE = re.compile(r"[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?")
TIMEZONE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+-]*(/[A-Za-z0-9_+-]+)*")
LOCALE_RE = re.compile(r"[A-Za-z]{2,3}_[A-Za-z]{2,4}(\.[A-Za-z0-9-]+)?")
KEYMAP_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


@dataclass
class Settings:
    mode: str = "bundled"
    template_url: str = ""
    template_token: str = ""
    template_branch: str = ""
    origin_url: str = ""
    origin_token: str = ""

    locale: str = paths.DEFAULT_LOCALE
    keymap: str = paths.DEFAULT_KEYMAP
    timezone: str = paths.DEFAULT_TIMEZONE
    hostname: str = paths.DEFAULT_HOSTNAME

    username: str = paths.DEFAULT_USERNAME
    fullname: str = ""
    password: str = ""
    shell: str = paths.DEFAULT_SHELL

    firmware: str = "efi"
    disk: str = ""
    disk_mode: str = "erase"
    disk_free_start: int = 0
    disk_free_end: int = 0
    filesystem: str = "ext4"
    swap: str = "none"
    encrypt: bool = False
    passphrase: str = ""
    serial_console: bool = False

    clone_relative: str = paths.DEFAULT_CLONE_RELATIVE
    final_action: str = "reboot"

    extras: dict = field(default_factory=dict)

    @classmethod
    def field_names(cls):
        return [item.name for item in fields(cls)]

    def to_json(self):
        return json.dumps(asdict(self), indent=2) + "\n"

    @classmethod
    def from_json(cls, text):
        known = set(cls.field_names())
        payload = json.loads(text)
        return cls(**{key: value for key, value in payload.items() if key in known})

    @classmethod
    def load(cls, path):
        return cls.from_json(open(path, encoding="utf-8").read())

    def save(self, path):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.to_json())

    def normalize(self):
        """A repository URL always means prepared mode.

        The default is bundled: with no URL the ISO installs the embedded
        ojuny-minimal-template.
        """
        if self.template_url.strip():
            self.mode = "prepared"
        return self

    def template_repository(self):
        """The repository the engine will install."""
        if self.template_url.strip():
            return self.template_url.strip()
        return "github:ojuny-project/ojuny-minimal-template (bundled)"


def _require(problems, screen, condition, message):
    if not condition:
        problems.append({"screen": screen, "message": message})


def validate(settings, firmware_available=None):
    """Return a list of {screen, message} problems. Empty means valid."""
    problems = []

    _require(
        problems,
        "template",
        settings.mode in TEMPLATE_MODES,
        "template mode must be bundled or prepared",
    )
    _require(
        problems,
        "template",
        settings.mode != "prepared" or settings.template_url.strip() != "",
        "a prepared template needs a repository URL",
    )
    _require(
        problems,
        "template",
        not settings.template_token or settings.template_url.startswith(
            ("http://", "https://")
        ),
        "a template token needs an HTTP(S) URL",
    )
    _require(
        problems,
        "origin",
        not settings.origin_token or settings.origin_url.startswith(("http://", "https://")),
        "an origin token needs an HTTP(S) URL",
    )

    _require(
        problems,
        "system",
        bool(LOCALE_RE.fullmatch(settings.locale)),
        "locale must look like en_US.UTF-8",
    )
    _require(
        problems,
        "system",
        bool(KEYMAP_RE.fullmatch(settings.keymap)),
        "keymap must be a console keymap name such as us",
    )
    _require(
        problems,
        "system",
        bool(TIMEZONE_RE.fullmatch(settings.timezone)),
        "timezone must look like Europe/Oslo or UTC",
    )
    _require(
        problems,
        "system",
        bool(HOSTNAME_RE.fullmatch(settings.hostname)),
        "hostname must start and end with a letter or digit",
    )
    _require(
        problems,
        "system",
        bool(USERNAME_RE.fullmatch(settings.username)),
        "username must start with a lower case letter or underscore",
    )
    _require(
        problems,
        "system",
        settings.username != "root",
        "the user account must not be root",
    )
    _require(
        problems,
        "system",
        settings.mode != "bundled" or len(settings.password) >= 8,
        "password must be at least 8 characters",
    )
    _require(
        problems,
        "system",
        settings.shell in paths.SHELLS,
        "shell must be one of {}".format(", ".join(paths.SHELLS)),
    )

    _require(problems, "disk", settings.disk != "", "select a target disk")
    _require(
        problems,
        "disk",
        settings.disk_mode in DISK_MODES,
        "disk mode must be erase or free",
    )
    _require(
        problems,
        "disk",
        settings.filesystem in FILESYSTEMS,
        "filesystem must be one of {}".format(", ".join(FILESYSTEMS)),
    )
    _require(
        problems,
        "disk",
        settings.swap in SWAP_CHOICES,
        "swap must be one of {}".format(", ".join(SWAP_CHOICES)),
    )
    _require(
        problems,
        "disk",
        not settings.encrypt or len(settings.passphrase) >= 8,
        "encryption passphrase must be at least 8 characters",
    )
    if firmware_available is not None:
        _require(
            problems,
            "disk",
            settings.firmware == firmware_available,
            "this machine booted {}, so firmware must be {}".format(
                firmware_available, firmware_available
            ),
        )
    _require(
        problems,
        "disk",
        settings.final_action in FINAL_ACTIONS,
        "final action must be reboot or poweroff",
    )
    _require(
        problems,
        "disk",
        bool(re.fullmatch(r"repos(?:/[A-Za-z0-9._-]+)+", settings.clone_relative)),
        "repository path must be a relative path such as repos/nix-flake",
    )
    return problems
