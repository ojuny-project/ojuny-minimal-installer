"""The install engine.

Phases are sequential and every phase is logged. On failure the engine stops at
the phase, keeps the target mounted and raises; the UI offers a shell.
"""

import re
import subprocess
import time

from . import disk, hardware, paths, preflight, postinstall, template

PHASES = (
    "checking the target",
    "preparing the template",
    "partitioning and formatting",
    "generating hardware",
    "installing NixOS",
    "finishing the configuration",
    "unmounting",
)

PROGRESS_LINE = re.compile(r"^(copying path|building|fetching|unpacking)")


class InstallError(Exception):
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
        raise InstallError(
            "command failed ({}): {}\n{}{}".format(
                result.returncode,
                " ".join(str(part) for part in command),
                result.stdout,
                result.stderr,
            )
        )
    return result.stdout


class Engine:
    def __init__(self, settings, reporter):
        self.settings = settings
        self.reporter = reporter
        self.total_phases = len(PHASES)
        self.started = time.monotonic()
        self.version = "unknown"

    def phase(self, index):
        self.reporter.set_phase(PHASES[index])
        self.reporter.advance(index, self.total_phases)

    def run(self):
        settings = self.settings
        paths.INSTALL_LOG.write_text("", encoding="utf-8")
        self.log("Ojuny minimal installer")
        self.log("started={}".format(time.strftime("%Y-%m-%d %H:%M:%S")))
        self.log("mode={} template={}".format(settings.mode, settings.template_repository()))

        self.phase(0)
        disk.validate_target(settings)
        self.wait_for_network()

        self.phase(1)
        staging = template.acquire(settings, self.reporter)
        self.log("staging={}".format(staging))
        host = self.resolve_host(staging)
        runtime_clone = "/home/{}/{}".format(settings.username, settings.clone_relative)
        if settings.mode == "bundled":
            hashed_password = self.hash_password(settings.password)
            prepared = template.prepare_bundled(
                staging, settings, runtime_clone, self.version, hashed_password, self.reporter
            )
            if not prepared:
                template.inject(
                    staging, settings, runtime_clone, self.version, hashed_password
                )
        self.log("host={}".format(host))

        self.phase(2)
        disk.prepare(settings, self.reporter)

        self.phase(3)
        hardware.prepare(staging, settings, self.reporter)

        message = (
            "Regenerate hardware for this machine"
            if settings.mode == "prepared"
            else "Initial Ojuny configuration"
        )
        template.git_init(staging, message)
        self.phase(4)
        self.settings.extras["boot_order_before"] = self.boot_order()
        self.nixos_install(staging, host)
        self.restore_boot_order()

        self.phase(5)
        postinstall.finish(self, staging, host)

        self.phase(6)
        disk.unmount()
        self.log("installation finished")
        self.reporter.advance(self.total_phases, self.total_phases)

    def resolve_host(self, staging):
        settings = self.settings
        if settings.mode == "prepared":
            detected = template.detect_username(staging)
            if detected:
                settings.username = detected
            settings.hostname = template.preferred_host(staging)
        self.version = template.state_version()
        self.log("state_version={}".format(self.version))
        return settings.hostname

    def hash_password(self, password):
        for method in ("yescrypt", "sha-512"):
            result = subprocess.run(
                ["mkpasswd", "-m", method, "--", password],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        raise InstallError("mkpasswd could not hash the password: {}".format(result.stderr.strip()))

    def wait_for_network(self, attempts=60):
        for _ in range(attempts):
            if preflight.network_available():
                return
            time.sleep(2)
        raise InstallError("network is not available; connect a wired connection and retry")

    def nixos_install(self, staging, host):
        self.log("installing {}#{}".format(staging, host))
        command = [
            "nixos-install",
            "--no-root-passwd",
            "--root",
            str(paths.TARGET),
            "--flake",
            "{}#{}".format(staging, host),
            "--option",
            "build-dir",
            "/nix/var/nix/builds",
        ]
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        tail = []
        items = 0
        for line in process.stdout:
            text = line.rstrip("\n")
            self.log(text)
            if PROGRESS_LINE.match(text):
                items += 1
                self.reporter.advance(items, 0)
            tail.append(text)
            if len(tail) > 60:
                del tail[:-60]
        code = process.wait()
        if code != 0:
            raise InstallError("nixos-install failed:\n{}".format("\n".join(tail)))

    def boot_order(self):
        try:
            return run(["efibootmgr"])
        except (InstallError, OSError):
            return ""

    def restore_boot_order(self):
        if self.settings.firmware != "efi":
            return
        before = self.settings.extras.get("boot_order_before")
        if before:
            order = re.search(r"^BootOrder:\s*([0-9A-Fa-f,]+)", before, re.MULTILINE)
            if order:
                run(["efibootmgr", "-o", order.group(1)], check=False)
                self.log("restored boot order {}".format(order.group(1)))
        after = self.boot_order()
        entry = None
        for line in after.splitlines():
            match = re.match(r"^Boot([0-9A-Fa-f]{4})\*?\s+Linux Boot Manager", line)
            if match:
                entry = match.group(1)
                break
        if not entry:
            return
        order_line = re.search(r"^BootOrder:\s*([0-9A-Fa-f,]+)", after, re.MULTILINE)
        if not order_line:
            return
        order = [item for item in order_line.group(1).split(",") if item and item != entry]
        run(["efibootmgr", "-o", ",".join([entry] + order)], check=False)
        self.log("moved Linux Boot Manager to the front")

    def log(self, text):
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        elapsed = time.monotonic() - self.started
        try:
            with open(paths.INSTALL_LOG, "a", encoding="utf-8") as handle:
                handle.write("{} +{:.3f}s {}\n".format(stamp, elapsed, text))
        except OSError:
            pass
        self.reporter.log(text)
