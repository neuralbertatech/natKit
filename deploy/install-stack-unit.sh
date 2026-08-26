#!/usr/bin/env bash
# Install and enable the systemd user unit that brings the natKit dev stack back
# after a reboot (TEC-NATKIT-71).
#
# ⚠️ RUN THIS ON THE HOST, not in the `dev` toolbox -- `loginctl` talks to the
# SYSTEM bus, which a toolbox does not share, and fails there with "System has
# not been booted with systemd as init system". (`systemctl --user` does work in
# the toolbox: /run/user/1000/bus is the host's user bus. Only loginctl does not.)
set -euo pipefail

unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
src="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/natkit-stack.service"

mkdir -p "$unit_dir"
install -m 0644 "$src" "$unit_dir/natkit-stack.service"
systemctl --user daemon-reload
systemctl --user enable natkit-stack.service

# Without linger the user manager exits at logout and takes the stack with it,
# which defeats the entire point of the unit. Idempotent; already set on aviendha
# since 2026-08-12.
loginctl enable-linger "$USER"

echo
echo "Installed and enabled. NOT started -- 'systemctl --user start natkit-stack'"
echo "runs 'podman-compose up -d', which RECREATES containers, so start it when"
echo "you are not mid-recording. It will come up on its own at the next boot."
echo
systemctl --user is-enabled natkit-stack.service
