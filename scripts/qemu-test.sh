#!/usr/bin/env bash
# Boot the test ISO, install to an empty disk, then boot the installed disk.
#
# The test ISO is a fixture: it runs ojuny-install --settings ... --yes with
# /dev/vda and powers off. Usage:
#
#   scripts/qemu-test.sh [workdir]
#
# Requires qemu, OVMF and KVM. Set ISO=/path to reuse a built image.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${1:-${TMPDIR:-/tmp}/ojuny-minimal-test}"
IMAGE_SIZE="40G"
INSTALL_TIMEOUT="${INSTALL_TIMEOUT:-5400}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-900}"

mkdir -p "$WORK"
RUN="$WORK/run-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN"

if [[ -z "${ISO:-}" ]]; then
  echo "building the test ISO"
  iso_dir="$(nix build "$ROOT#ojuny-minimal-iso-test" --no-link --print-out-paths)"
  ISO="$(echo "$iso_dir"/iso/*.iso)"
fi
if [[ ! -f "$ISO" ]]; then
  echo "ISO not found: $ISO" >&2
  exit 1
fi

OVMF="$(nix build nixpkgs#OVMF.fd --no-link --print-out-paths)"
DISK="$RUN/target.qcow2"
VARS="$RUN/OVMF_VARS.fd"
INSTALL_LOG="$RUN/install-console.log"
BOOT_LOG="$RUN/boot-console.log"

qemu-img create -f qcow2 "$DISK" "$IMAGE_SIZE" >/dev/null
cp "$OVMF/FV/OVMF_VARS.fd" "$VARS"
chmod u+w "$VARS"

qemu_args=(
  -accel "${ACCEL:-kvm}"
  -m 6144
  -smp 4
  -display none
  -monitor none
  -no-reboot
  -drive "if=pflash,format=raw,readonly=on,file=$OVMF/FV/OVMF_CODE.fd"
  -drive "if=pflash,format=raw,file=$VARS"
  -netdev user,id=net0
  -device virtio-net-pci,netdev=net0
)

echo "installing to $DISK"
set +e
timeout "$INSTALL_TIMEOUT" qemu-system-x86_64 "${qemu_args[@]}" -serial "file:$INSTALL_LOG" \
  -drive file="$ISO",media=cdrom,readonly=on \
  -drive file="$DISK",if=virtio
install_status=$?
set -e
if [[ "$install_status" -ne 0 ]]; then
  echo "install run exited with $install_status" >&2
  tail -n 40 "$INSTALL_LOG" >&2
  exit 1
fi
if ! grep -q "installation finished" "$INSTALL_LOG"; then
  echo "the installer did not report completion" >&2
  tail -n 40 "$INSTALL_LOG" >&2
  exit 1
fi

echo "booting the installed disk"
set +e
timeout "$BOOT_TIMEOUT" qemu-system-x86_64 "${qemu_args[@]}" -serial "file:$BOOT_LOG" \
  -drive file="$DISK",if=virtio &
qemu_pid=$!
deadline=$((SECONDS + BOOT_TIMEOUT))
while ((SECONDS < deadline)); do
  if grep -q "login:" "$BOOT_LOG" 2>/dev/null; then
    break
  fi
  if ! kill -0 "$qemu_pid" 2>/dev/null; then
    break
  fi
  sleep 5
done
kill "$qemu_pid" 2>/dev/null || true
wait "$qemu_pid" 2>/dev/null
set -e

if ! grep -q "login:" "$BOOT_LOG"; then
  echo "the installed system did not reach a login prompt" >&2
  tail -n 40 "$BOOT_LOG" >&2
  exit 1
fi

echo "ok: the installed system boots"
echo "logs: $INSTALL_LOG $BOOT_LOG"
