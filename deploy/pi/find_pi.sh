#!/usr/bin/env bash
# Find the Pi on the local network WITHOUT a .local (mDNS) lookup, and print instant addresses.
#
# Why: on a phone hotspot that is IPv6-only, macOS never takes an IPv4 address, and every lookup of
# hack-knight.local then waits ~5 s for an IPv4 answer that cannot come. IPv6 neighbor discovery
# finds the Pi directly, and its link-local address (derived from its hardware address) never changes.
#
#   deploy/pi/find_pi.sh                          print addresses and ready-to-paste URLs
#   deploy/pi/find_pi.sh --ssh-config HOSTNAME    also make `ssh pi@HOSTNAME` use the stable address
#   deploy/pi/find_pi.sh --remove-ssh-config HOSTNAME
#
# Works on macOS (ndp) and Linux (ip -6 neigh). Needs the Mac and the Pi on the same network.
set -euo pipefail

IFACE="${PI_IFACE:-}"
MODE=show
HOST=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ssh-config) MODE=add; HOST="${2:?hostname required}"; shift ;;
    --remove-ssh-config) MODE=remove; HOST="${2:?hostname required}"; shift ;;
    -h|--help) sed -n 2,13p "$0"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

SSH_CONFIG="$HOME/.ssh/config"
BEGIN="# BEGIN cradleecho pi $HOST (managed by deploy/pi/find_pi.sh)"
END="# END cradleecho pi $HOST"

remove_block() {
  [[ -f "$SSH_CONFIG" ]] || return 0
  local tmp; tmp=$(mktemp)
  awk -v b="$BEGIN" -v e="$END" '$0==b{skip=1} !skip{print} $0==e{skip=0}' "$SSH_CONFIG" > "$tmp"
  cat "$tmp" > "$SSH_CONFIG"; rm -f "$tmp"
}

if [[ "$MODE" == remove ]]; then
  remove_block; echo "Removed the ssh config block for $HOST."; exit 0
fi

# Pick the Wi-Fi/Ethernet interface carrying the default route.
if [[ -z "$IFACE" ]]; then
  if [[ "$(uname -s)" == Darwin ]]; then IFACE=$(route -n get default 2>/dev/null | awk '/interface:/{print $2}')
  else IFACE=$(ip route show default 2>/dev/null | awk '/default/{print $5; exit}'); fi
  IFACE="${IFACE:-en0}"
fi

# Wake the neighbor cache: ask every IPv6 host on the link to answer.
if [[ "$(uname -s)" == Darwin ]]; then
  ping6 -c 2 -t 3 "ff02::1%$IFACE" >/dev/null 2>&1 || true
  NEIGH=$(ndp -an 2>/dev/null | awk '{print $1, $2}')
else
  ping -6 -c 2 -W 3 "ff02::1%$IFACE" >/dev/null 2>&1 || true
  NEIGH=$(ip -6 neigh show dev "$IFACE" 2>/dev/null | awk '{print $1, $5}')
fi

# Raspberry Pi Foundation hardware-address prefixes.
PI_OUI='^(b8:27:eb|dc:a6:32|e4:5f:01|d8:3a:dd|2c:cf:67|28:cd:c1)'
MATCHES=$(echo "$NEIGH" | awk -v re="$PI_OUI" 'tolower($2) ~ re {print $1}')

LINK_LOCAL=$(echo "$MATCHES" | grep -i '^fe80' | head -1 | sed 's/%.*//' || true)
GLOBAL=$(echo "$MATCHES" | grep -v -i '^fe80' | head -1 || true)

if [[ -z "$LINK_LOCAL" && -z "$GLOBAL" ]]; then
  echo "No Raspberry Pi found on $IFACE. Is the Pi powered on and on the same network (hotspot) as this machine?" >&2
  exit 1
fi

echo "Raspberry Pi found on $IFACE:"
[[ -n "$LINK_LOCAL" ]] && echo "  link-local (stable, ssh):  ${LINK_LOCAL}%${IFACE}"
[[ -n "$GLOBAL" ]]     && echo "  global (changes if the hotspot reconnects): $GLOBAL"
echo
[[ -n "$LINK_LOCAL" ]] && echo "  ssh:        ssh pi@${LINK_LOCAL}%${IFACE}"
if [[ -n "$GLOBAL" ]]; then
  echo "  web UI:     http://[${GLOBAL}]:3000"
  echo "  daemon:     http://[${GLOBAL}]:8000/healthz"
  echo "  video feed: http://[${GLOBAL}]:8000/video_feed"
else
  echo "  (no global IPv6 address yet; the web UI needs one. Try again in a few seconds.)"
fi

if [[ "$MODE" == add ]]; then
  [[ -n "$LINK_LOCAL" ]] || { echo "Can't write the ssh config without a link-local address." >&2; exit 1; }
  mkdir -p "$HOME/.ssh"; touch "$SSH_CONFIG"; chmod 600 "$SSH_CONFIG"
  remove_block
  {
    echo
    echo "$BEGIN"
    echo "Host $HOST"
    echo "    HostName ${LINK_LOCAL}%%${IFACE}"   # ssh_config treats % as an escape, so the zone separator is written %%
    echo "    HostKeyAlias $HOST"
    echo "$END"
  } >> "$SSH_CONFIG"
  echo
  echo "ssh now reaches 'ssh pi@$HOST' through ${LINK_LOCAL}%${IFACE} with no name lookup."
  echo "Undo with: deploy/pi/find_pi.sh --remove-ssh-config $HOST"
fi
