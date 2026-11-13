# Screen flow

The installer runs on the console started by `systemd.services.ojuny-minimal-install`.
It is one full-screen TUI built from presentation rows. No mouse, no
graphical toolkit.

## Keys

| Key | Action |
| --- | --- |
| `up`, `k` | previous row |
| `down`, `j` | next row |
| `enter` | edit the row, accept the prompt, or advance an information row |
| `left`, `h` / `right`, `l` | change a choice or toggle |
| `n`, `tab` | next screen |
| `p` | previous screen |
| `q`, `ctrl-c` | quit to a root shell |
| `esc` | cancel the current text prompt |
| `ctrl-u` | clear the current text prompt |

## Screens

1. Welcome. Machine model, firmware, memory, CPU count, network state and the
   number of eligible disks. Missing commands or less than 3.5 GiB of RAM stop
   the installer. No network loops on retry.
2. Template. `Template source` is `bundled` or `prepared`. An empty repository
   URL installs the bundled `ojuny-minimal-template`. A URL switches to a
   prepared install of that repository. `Access token` and `Branch` are
   optional.
3. Git origin. Optional origin URL and token for the installed configuration.
   Empty means no remote. A token only applies to an HTTP(S) URL and is stored
   as `~/.git-credentials` with mode `0600`.
4. System. Locale, console keymap, timezone, hostname, username, full name,
   password, password confirmation, shell.
5. Disk. Firmware, target disk, disk mode (`erase` or `free`), free space,
   filesystem, swap, LUKS2 root, passphrase, serial console, final action. The
   free-space row shows the largest region that fits the 30 GiB minimum.
6. Summary. Read-only recap of every value that reaches the engine. Enter asks
   for the final confirmation (`install`, `go back`, `quit`).
7. Progress. Current phase, completed phases, a rolling log tail and a store
   path counter. The install cannot be cancelled here.
8. Failure. The error, the log path and an offer to start a root shell. The
   target stays mounted for inspection.
9. Finished. The configuration path and the install log location, then reboot
   or power off.

Validation runs when a screen advances and only reports problems that belong
to that screen, so an error is shown next to the value that caused it.

## Prepared templates

A prepared repository keeps its own user, hostname and configuration modules.
The installer only regenerates the hardware and bootloader modules, writes the
host imports and installs. The username and hostname entered on the System
screen are ignored for a prepared install; the Summary screen still shows them,
and the engine replaces them with the values it reads from the repository.
