#!/bin/bash
# Idempotent setup INSIDE the herdr-workspace container (run as agent):
#   podman exec -i herdr-workspace bash -s < herdr-workspace-setup.sh
# Installs the reviewed herdr plugins at pinned commits and applies their safe config.
# Bump a pin only after re-reviewing that plugin (third-party code running as you).
set -euo pipefail

PLUGINS=(
  "herdr-file-viewer           smarzban/herdr-file-viewer                       d17a068ee753daf5ba205bafd59c130b81b8c6c0"
  "herdr-sidebar               alexarthurs/herdr-sidebar/plugins/herdr-sidebar  081ed133f3faa377438b51ce435fe8a87c439593"
  "ray.plugin-manager          speardragon/herdr-plugin-manager                 8ed222ab7efe735b3ef5e037e7ee81d6d7650e4e"
  "chmarax.herdr-nvim          ChmaraX/herdr-nvim                               88a68c77fe82476bdfcba39d36c3fa37109f35a8"
  "herdr-agent-usage           levi-qiao/herdr-agent-usage                      af2ac5e3d0c23b07362eadf757cf7e1196d3f1ee"
  "herdr-web-browser           MattJColes/herdr-web-browser                     b409c5f2625676964e21ad54ff6a6627abb05e3b"
)

# herdr-web-browser: use the image's signed Chrome, and make its startup believe Chrome
# for Testing is installed so it never runs its unverified ~200 MB download.
cfg=~/.config/herdr/plugins/config/herdr-web-browser
cft=~/.local/state/herdr/plugins/herdr-web-browser/chrome-for-testing/chrome-linux64
mkdir -p "$cfg" "$cft"
grep -qs '^chrome_path' "$cfg/config.toml" || printf 'chrome_path = "/usr/bin/google-chrome"\n' >> "$cfg/config.toml"
ln -sfn /usr/bin/google-chrome "$cft/chrome"

installed=$(herdr plugin list --json </dev/null | jq -r '.result.plugins[] | "\(.plugin_id) \(.source.resolved_commit // "")"')
for p in "${PLUGINS[@]}"; do
  read -r id repo ref <<<"$p"
  if grep -qx "$id $ref" <<<"$installed"; then echo "ok        $id"; continue; fi
  echo "install   $id @ ${ref:0:12}"
  herdr plugin install "$repo" --ref "$ref" -y </dev/null >/dev/null
done

# herdr-agent-usage: only ever look at Claude (no other vendors' credential files).
au=$(herdr plugin config-dir herdr-agent-usage </dev/null | tail -1)
mkdir -p "$au"; echo "only,claude" > "$au/agents"
herdr plugin list </dev/null | grep -E '^- '
