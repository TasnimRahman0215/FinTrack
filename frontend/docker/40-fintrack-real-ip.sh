#!/bin/sh
# Runs at container start (nginx images execute /docker-entrypoint.d/*.sh before nginx starts).
#
# TRUSTED_PROXIES: comma-separated IPs/CIDRs of reverse proxies in front of this container
# (Caddy, Tailscale serve, a load balancer...). Only requests coming *from* those addresses may
# tell nginx the real client IP through X-Forwarded-For; everyone else's header is ignored.
# The backend rate-limits logins per client IP, so without this every user behind such a proxy
# would share one IP (and one limit). Leave it empty when browsers connect to this container
# directly.
set -eu

out=/etc/nginx/conf.d/real-ip.conf
: > "$out"

if [ -z "${TRUSTED_PROXIES:-}" ]; then
    exit 0
fi

for proxy in $(echo "$TRUSTED_PROXIES" | tr ',' ' '); do
    case "$proxy" in
        *[!0-9A-Fa-f.:/]*)
            echo "TRUSTED_PROXIES: '$proxy' is not an IP address or CIDR range" >&2
            exit 1
            ;;
    esac
    echo "set_real_ip_from $proxy;" >> "$out"
done
echo "real_ip_header X-Forwarded-For;" >> "$out"
echo "real_ip_recursive on;" >> "$out"
echo "Trusting X-Forwarded-For from: $TRUSTED_PROXIES"
