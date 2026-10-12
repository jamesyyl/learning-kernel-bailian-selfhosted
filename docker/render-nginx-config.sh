#!/bin/sh
set -eu

secret=${BAILIAN_SERVICE_BINDING_SECRET:-}
if [ "${#secret}" -ne 64 ]; then
    echo "BAILIAN_SERVICE_BINDING_SECRET must be 64 hexadecimal characters." >&2
    exit 1
fi
case "$secret" in
    *[!0123456789abcdefABCDEF]*)
        echo "BAILIAN_SERVICE_BINDING_SECRET must be 64 hexadecimal characters." >&2
        exit 1
        ;;
esac

sed "s/__BAILIAN_SERVICE_BINDING_SECRET__/${secret}/g" \
    /etc/bailian/nginx.conf.template \
    > /etc/nginx/conf.d/default.conf
