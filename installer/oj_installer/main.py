"""Entry point and screen state machine."""

import argparse
import curses
import os
import subprocess
import sys
import time

from . import paths, preflight, screens, settings as settings_module, tui
from .install import Engine


class PrintReporter:
    def __init__(self):
        self.started = time.monotonic()

    def set_phase(self, text):
        print("==> {}".format(text), flush=True)

    def log(self, text):
        print(text, flush=True)

    def advance(self, done, total):
        if total:
            print("[{}/{}]".format(done, total), flush=True)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="ojuny-install",
        description="Install an Ojuny template from a console.",
    )
    parser.add_argument(
        "--settings",
        metavar="FILE",
        help="pre-fill the screens from a JSON settings file",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="run the install without screens; used by the test rig",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="print the preflight summary and exit",
    )
    parser.add_argument("--version", action="version", version="ojuny-minimal-installer 0.1.0")
    return parser.parse_args(argv)


def preflight_text():
    summary = preflight.summary()
    lines = [
        "model: {}".format(summary["model"]),
        "firmware: {}".format(summary["firmware"]),
        "memory: {:.1f} GiB".format(summary["ram"] / 1024**3),
        "cpus: {}".format(summary["cpus"]),
        "network: {}".format("ok" if summary["network"] else "unavailable"),
        "missing commands: {}".format(", ".join(summary["missing"]) or "none"),
        "eligible disks:",
    ]
    for candidate in summary["disks"]:
        lines.append(
            "  {} {:.1f} GiB {}".format(
                candidate["path"], candidate["size"] / 1024**3, candidate["model"]
            )
        )
    for path, reason in summary["skipped"]:
        lines.append("  skipped {}: {}".format(path, reason))
    return "\n".join(lines)


def run_scripted(settings):
    settings.normalize()
    problems = settings_module.validate(settings, preflight.firmware_available())
    if problems:
        for problem in problems:
            print("{}: {}".format(problem["screen"], problem["message"]), file=sys.stderr)
        return 1
    engine = Engine(settings, PrintReporter())
    try:
        engine.run()
    except Exception as error:
        print("installation failed: {}".format(error), file=sys.stderr)
        print("log: {}".format(paths.INSTALL_LOG), file=sys.stderr)
        return 1
    final_action(settings.final_action)
    return 0


def drop_to_shell():
    try:
        curses.endwin()
    except curses.error:
        pass
    os.execv("/bin/bash", ["/bin/bash", "-i"])


def final_action(action):
    subprocess.run(["sync"], check=False)
    subprocess.run(["systemctl", action], check=False)


def interface(app, settings):
    summary = preflight.summary()
    steps = [
        ("Welcome", lambda: screens.welcome(app, settings, summary)),
        ("Template", lambda: screens.template(app, settings)),
        ("Git origin", lambda: screens.origin(app, settings)),
        ("System", lambda: screens.system(app, settings)),
        ("Disk", lambda: screens.disk(app, settings, summary)),
        ("Summary", lambda: screens.summary(app, settings)),
    ]
    index = 0
    while index < len(steps):
        action = steps[index][1]()
        if action == "next":
            index += 1
        elif action == "back":
            index = max(1, index - 1)
        else:
            return "shell"

    while True:
        choice = app.prompt_choice(
            "Install {} to {}?".format(settings.template_repository(), settings.disk),
            ["install", "go back", "quit"],
            2,
        )
        if choice == "install":
            break
        if choice == "go back":
            if steps[-1][1]() != "next":
                return "shell"
            continue
        return "shell"

    reporter = tui.Reporter()
    engine = Engine(settings, reporter)
    status, error = tui.run_progress(app, "Installing NixOS", engine.run, reporter)
    if status != "done":
        app.message(
            "Installation failed",
            "{}\n\nThe target is left mounted for inspection.\nLog: {}".format(
                error, paths.INSTALL_LOG
            ),
            "press enter for a root shell",
        )
        return "shell"

    app.message(
        "Installation finished",
        "Configuration: /home/{}/{}\nLog: ~/ojuny-install.log".format(
            settings.username, settings.clone_relative
        ),
        "press enter to choose the final action",
    )
    return settings.final_action


def run_ui(settings):
    try:
        result = curses.wrapper(interface, settings)
    except KeyboardInterrupt:
        result = "shell"
    except Exception as error:  # curses setup failures must not kill the console
        print("the installer UI could not start: {}".format(error), file=sys.stderr)
        result = "shell"
    if result in ("reboot", "poweroff"):
        final_action(result)
        return 0
    drop_to_shell()
    return 0


def main(argv=None):
    args = parse_args(argv)
    if args.check:
        print(preflight_text())
        return 0

    settings = settings_module.Settings()
    if args.settings:
        try:
            settings = settings_module.Settings.load(args.settings)
        except (OSError, ValueError) as error:
            print("could not read {}: {}".format(args.settings, error), file=sys.stderr)
            return 2

    if args.yes:
        return run_scripted(settings)
    if os.geteuid() != 0:
        print("the installer must run as root", file=sys.stderr)
        return 2
    return run_ui(settings)


if __name__ == "__main__":
    sys.exit(main())
