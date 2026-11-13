"""Fixed paths and constants.

Every path the installer reads or writes lives here. The fixed-paths check
rejects template-relative paths anywhere else in the installer.
"""

from pathlib import Path

LIVE_TEMPLATE = Path("/etc/ojuny/flake")
LIVE_TEMPLATE_REVISION = Path("/etc/ojuny/template-revision")
LIVE_HELPERS = Path("/etc/ojuny/helpers.json")

TARGET = Path("/mnt")
TARGET_ETC = TARGET / "etc"
TARGET_NIXOS = TARGET_ETC / "nixos"
TARGET_PASSWD = TARGET_ETC / "passwd"

STAGING_PREFIX = "ojuny-stage-"
INSTALL_LOG = Path("/tmp/ojuny-install.log")
INSTALL_REPORT = Path("/tmp/ojuny-install-report.json")

DEFAULT_CLONE_RELATIVE = "repos/nix-flake"
DEFAULT_LOCALE = "en_US.UTF-8"
DEFAULT_KEYMAP = "us"
DEFAULT_TIMEZONE = "UTC"
DEFAULT_USERNAME = "user"
DEFAULT_HOSTNAME = "ojuny"
DEFAULT_SHELL = "zsh"
SHELLS = ("zsh", "bash", "fish")

MIN_RAM_BYTES = int(3.5 * 1024**3)
MIN_DISK_BYTES = 30 * 1024**3
ESP_BYTES = 4 * 1024**3
BIOS_BOOT_BYTES = 1024**2
SMALL_SWAP_BYTES = 4 * 1024**3
SECTOR_BYTES = 512
ALIGN_SECTORS = 2048

NETWORK_CHECK_URL = ("cache.nixos.org", 443)

REQUIRED_COMMANDS = (
    "btrfs",
    "cryptsetup",
    "efibootmgr",
    "findmnt",
    "git",
    "lsblk",
    "mkfs.btrfs",
    "mkfs.ext4",
    "mkfs.f2fs",
    "mkfs.vfat",
    "mkfs.xfs",
    "mkswap",
    "mkpasswd",
    "mount",
    "nix",
    "nixos-facter",
    "nixos-generate-config",
    "nixos-install",
    "parted",
    "partprobe",
    "sgdisk",
    "udevadm",
    "umount",
)

LUKS_NAME = "cryptroot"
LUKS_KEYFILE = "crypto_keyfile.bin"
