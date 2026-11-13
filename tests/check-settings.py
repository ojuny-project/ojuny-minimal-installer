#!/usr/bin/env python3
"""Settings validation and JSON round-trip checks."""

import sys

from oj_installer import settings as settings_module

FAILURES = []


def check(name, condition, detail=""):
    if not condition:
        FAILURES.append("{}: {}".format(name, detail or "failed"))


def problems(record, firmware=None):
    return {item["screen"] for item in settings_module.validate(record, firmware)}


def base():
    return settings_module.Settings(
        mode="bundled",
        username="user",
        hostname="ojuny",
        password="password12",
        disk="/dev/disk/by-id/disk",
        disk_mode="erase",
    )


def main():
    record = base()
    check("valid bundled", problems(record) == set(), str(problems(record)))

    record = base()
    record.mode = "prepared"
    check("prepared needs a URL", "template" in problems(record))
    record.template_url = "https://example.com/template"
    check("prepared with URL", problems(record) == set(), str(problems(record)))
    check("prepared ignores the password", problems(
        settings_module.Settings(
            mode="prepared",
            template_url="https://example.com/x",
            username="user",
            hostname="ojuny",
            password="",
            disk="/dev/disk/by-id/disk",
        )
    ) == set())

    record = base()
    record.template_token = "token"
    check("token needs http", "template" in problems(record))
    record.template_url = "git@example.com:x/y"
    check("token rejects ssh", "template" in problems(record))

    record = base()
    record.origin_token = "token"
    check("origin token needs http", "origin" in problems(record))

    record = base()
    record.username = "Root"
    check("username rules", "system" in problems(record))
    record = base()
    record.hostname = "-bad"
    check("hostname rules", "system" in problems(record))
    record = base()
    record.password = "short"
    check("password length", "system" in problems(record))

    record = base()
    record.disk = ""
    check("disk required", "disk" in problems(record))
    record = base()
    record.filesystem = "zfs"
    check("filesystem rules", "disk" in problems(record))
    record = base()
    record.encrypt = True
    record.passphrase = "short"
    check("passphrase length", "disk" in problems(record))
    record.passphrase = "longenough"
    check("encryption valid", problems(record) == set(), str(problems(record)))

    record = base()
    check("firmware mismatch", "disk" in problems(record, firmware="bios"))

    record = base()
    record.template_url = ""
    record.normalize()
    check("normalize bundled", record.mode == "bundled")
    record.template_url = "https://example.com/x"
    record.normalize()
    check("normalize prepared", record.mode == "prepared")
    check("repository label", record.template_repository() == "https://example.com/x")

    record = base()
    record.fullname = "Test User"
    round_trip = settings_module.Settings.from_json(record.to_json())
    check("json round trip", round_trip.to_json() == record.to_json())

    if FAILURES:
        for failure in FAILURES:
            print(failure, file=sys.stderr)
        return 1
    print("settings: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
