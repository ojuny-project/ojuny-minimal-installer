"""Screen definitions.

Each screen edits one part of the settings record and validates only its own
fields, so an error is shown where the bad value lives.
"""

from . import disk as disk_module
from . import paths, preflight, settings as settings_module, tui


def _problems_for(settings, screen):
    return [
        problem
        for problem in settings_module.validate(settings, preflight.firmware_available())
        if problem["screen"] == screen
    ]


def run_screen(app, title, fields, screen, settings, subtitle=None, footer=None):
    error = None
    while True:
        action = app.run_screen(title, fields, subtitle, error, footer)
        if action != "next":
            return action
        problems = _problems_for(settings, screen)
        if not problems:
            return "next"
        error = problems[0]["message"]


def welcome(app, settings, summary):
    disks = summary["disks"]
    network = "reachable" if summary["network"] else "not reachable"
    body = [
        "This ISO installs an Ojuny template to a local disk.",
        "",
        "Machine:   {}".format(summary["model"]),
        "Firmware:  {}".format(preflight.firmware_label(summary["firmware"])),
        "Memory:    {:.1f} GiB".format(summary["ram"] / 1024**3),
        "CPUs:      {}".format(summary["cpus"]),
        "Network:   {}".format(network),
        "Disks:     {} eligible".format(len(disks)),
        "",
        "The default template is ojuny-minimal-template, embedded in this ISO.",
        "Enter a repository URL on the template screen to install a fork.",
    ]
    if summary["missing"]:
        body += ["", "Missing commands: " + ", ".join(summary["missing"])]
    app.message("Welcome", "\n".join(body))

    if summary["missing"]:
        app.message(
            "Broken live image",
            "Required commands are missing: {}\nThe installer cannot continue."
            .format(", ".join(summary["missing"])),
            "press enter to quit",
        )
        return "quit"
    if summary["ram"] < paths.MIN_RAM_BYTES:
        app.message(
            "Not enough memory",
            "The installer needs at least 3.5 GiB of RAM, found {:.1f} GiB."
            .format(summary["ram"] / 1024**3),
            "press enter to quit",
        )
        return "quit"

    while not preflight.network_available():
        choice = app.prompt_choice(
            "No network. Connect a wired connection.",
            ["retry", "quit"],
            0,
        )
        if choice != "retry":
            return "quit"
    return "next"


def template(app, settings):
    fields = [
        tui.Field("mode", "Template source", "choice", lambda: settings.mode,
                  lambda value: setattr(settings, "mode", value),
                  ["bundled", "prepared"],
                  "bundled installs the template embedded in this ISO"),
        tui.Field("url", "Repository URL", "text", lambda: settings.template_url,
                  lambda value: setattr(settings, "template_url", value),
                  help="empty installs ojuny-minimal-template; a URL installs that repository"),
        tui.Field("token", "Access token", "secret", lambda: settings.template_token,
                  lambda value: setattr(settings, "template_token", value),
                  help="HTTP(S) only; written to ~/.git-credentials with mode 0600"),
        tui.Field("branch", "Branch", "text", lambda: settings.template_branch,
                  lambda value: setattr(settings, "template_branch", value),
                  help="empty uses the repository default branch"),
    ]
    return run_screen(
        app,
        "Template",
        fields,
        "template",
        settings,
        "No repository URL means the bundled ojuny-minimal-template.",
    )


def origin(app, settings):
    fields = [
        tui.Field("url", "Origin URL", "text", lambda: settings.origin_url,
                  lambda value: setattr(settings, "origin_url", value),
                  help="optional git remote for the installed configuration"),
        tui.Field("token", "Origin token", "secret", lambda: settings.origin_token,
                  lambda value: setattr(settings, "origin_token", value),
                  help="HTTP(S) only; leaves no remote when both fields are empty"),
    ]
    return run_screen(
        app,
        "Git origin",
        fields,
        "origin",
        settings,
        "The installed flake is committed either way. The origin is optional.",
    )


def system(app, settings):
    confirmation = {"value": ""}
    fields = [
        tui.Field("locale", "Locale", "text", lambda: settings.locale,
                  lambda value: setattr(settings, "locale", value)),
        tui.Field("keymap", "Console keymap", "text", lambda: settings.keymap,
                  lambda value: setattr(settings, "keymap", value)),
        tui.Field("timezone", "Timezone", "text", lambda: settings.timezone,
                  lambda value: setattr(settings, "timezone", value)),
        tui.Field("hostname", "Hostname", "text", lambda: settings.hostname,
                  lambda value: setattr(settings, "hostname", value)),
        tui.Field("username", "Username", "text", lambda: settings.username,
                  lambda value: setattr(settings, "username", value)),
        tui.Field("fullname", "Full name", "text", lambda: settings.fullname,
                  lambda value: setattr(settings, "fullname", value),
                  help="display name; defaults to the username"),
        tui.Field("password", "Password", "secret", lambda: settings.password,
                  lambda value: setattr(settings, "password", value)),
        tui.Field("confirm", "Repeat password", "secret", lambda: confirmation["value"],
                  lambda value: confirmation.__setitem__("value", value)),
        tui.Field("shell", "Shell", "choice", lambda: settings.shell,
                  lambda value: setattr(settings, "shell", value),
                  list(paths.SHELLS)),
    ]
    error = None
    while True:
        action = app.run_screen(
            "System",
            fields,
            "Locale, keymap, timezone, hostname and the primary account.",
            error,
        )
        if action != "next":
            return action
        problems = _problems_for(settings, "system")
        if settings.password != confirmation["value"]:
            problems = [{"message": "the two passwords do not match"}] + problems
        if not problems:
            return "next"
        error = problems[0]["message"]


def disk(app, settings, summary):
    disk_options = []
    for candidate in summary["disks"]:
        label = "{}  {:.0f} GiB  {}".format(
            candidate["path"], candidate["size"] / 1024**3, candidate["model"]
        )
        disk_options.append(label)
    by_label = {label: candidate for label, candidate in zip(disk_options, summary["disks"])}

    def current_disk():
        for label, candidate in by_label.items():
            if candidate["path"] == settings.disk:
                return label
        return disk_options[0] if disk_options else "none"

    def set_disk(label):
        candidate = by_label.get(label)
        if candidate:
            settings.disk = candidate["path"]
            settings.extras["disk_real"] = candidate["real"]
            settings.extras["disk_size"] = candidate["size"]

    if disk_options and not settings.disk:
        set_disk(disk_options[0])

    fields = [
        tui.Field("firmware", "Firmware", "choice", lambda: settings.firmware,
                  lambda value: setattr(settings, "firmware", value),
                  list(settings_module.FIRMWARE_CHOICES),
                  "detected from the running machine"),
        tui.Field("disk", "Target disk", "choice", current_disk, set_disk,
                  disk_options or ["no eligible disk"]),
        tui.Field("mode", "Disk mode", "choice", lambda: settings.disk_mode,
                  lambda value: setattr(settings, "disk_mode", value),
                  ["erase", "free"],
                  "erase wipes the disk; free uses unallocated space only"),
        tui.Field("free", "Free space", "info",
                  lambda: disk_module.describe_free_region(settings)),
        tui.Field("filesystem", "Filesystem", "choice", lambda: settings.filesystem,
                  lambda value: setattr(settings, "filesystem", value),
                  list(settings_module.FILESYSTEMS)),
        tui.Field("swap", "Swap", "choice", lambda: settings.swap,
                  lambda value: setattr(settings, "swap", value),
                  list(settings_module.SWAP_CHOICES)),
        tui.Field("encrypt", "Encrypt root", "bool", lambda: settings.encrypt,
                  lambda value: setattr(settings, "encrypt", value),
                  help="LUKS2 on the root partition; swap is not encrypted"),
        tui.Field("passphrase", "Passphrase", "secret", lambda: settings.passphrase,
                  lambda value: setattr(settings, "passphrase", value)),
        tui.Field("serial", "Serial console", "bool", lambda: settings.serial_console,
                  lambda value: setattr(settings, "serial_console", value),
                  help="also start a getty on ttyS0 in the installed system"),
        tui.Field("final", "When finished", "choice", lambda: settings.final_action,
                  lambda value: setattr(settings, "final_action", value),
                  ["reboot", "poweroff"]),
    ]
    if not disk_options:
        app.message(
            "No eligible disk",
            "No internal disk of at least 30 GiB is available.\n\n"
            + "\n".join("{}: {}".format(path, reason) for path, reason in summary["skipped"]),
            "press enter to quit",
        )
        return "quit"
    return run_screen(
        app,
        "Disk",
        fields,
        "disk",
        settings,
        "Free space installs alongside existing systems without shrinking them.",
    )


def summary(app, settings):
    settings.normalize()
    region = disk_module.resolve_free_region(settings)
    settings.extras["free_region"] = region

    rows = [
        ("Template", settings.template_repository()),
        ("Branch", settings.template_branch or "default"),
        ("Origin", settings.origin_url or "none"),
        ("Locale", settings.locale),
        ("Keymap", settings.keymap),
        ("Timezone", settings.timezone),
        ("Hostname", settings.hostname),
        ("User", "{} ({})".format(settings.username, settings.fullname or settings.username)),
        ("Shell", settings.shell),
        ("Firmware", settings.firmware),
        ("Disk", settings.disk),
        ("Disk mode", settings.disk_mode),
        ("Region", "whole disk" if settings.disk_mode == "erase" else disk_module.describe_region(region)),
        ("Filesystem", settings.filesystem),
        ("Swap", settings.swap),
        ("Encryption", "LUKS2 root" if settings.encrypt else "none"),
        ("Serial console", "yes" if settings.serial_console else "no"),
        ("Finished", settings.final_action),
    ]
    fields = [
        tui.Field(key, label, "info", (lambda value=value: value))
        for key, label, value in ((key, label, value) for key, label, value in rows)
    ]
    return run_screen(
        app,
        "Summary",
        fields,
        "summary",
        settings,
        "The target disk is written only after the final confirmation.",
        "enter confirm   p back   q quit",
    )
