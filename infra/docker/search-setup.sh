#!/usr/bin/env bash
# Local Compose bootstrap only; never provisions application API keys or policies.
set -euo pipefail
umask 027

case "${1:-}" in
  certificates)
    cd /usr/share/elasticsearch
    mkdir -p /state/certs /kibana-config
    # Keep passwords stable across restarts. Never print them in setup logs.
    for secret in elastic_password kibana_password security_key reporting_key saved_objects_key; do
      if [ ! -s "/state/$secret" ]; then
        od -v -An -N24 -tx1 /dev/urandom | tr -d ' \n' > "/state/$secret"
      fi
    done
    if [ ! -s /state/certs/ca/ca.crt ]; then
      bin/elasticsearch-certutil ca --silent --pem --days 1095 --out /state/certs/ca.zip
      unzip -qo /state/certs/ca.zip -d /state/certs
    fi
    if [ ! -s /state/certs/elasticsearch/elasticsearch.crt ]; then
      bin/elasticsearch-certutil cert --silent --pem --days 1095 \
        --name elasticsearch --dns elasticsearch,localhost --ip 127.0.0.1 \
        --ca-cert /state/certs/ca/ca.crt --ca-key /state/certs/ca/ca.key \
        --out /state/certs/elasticsearch.zip
      unzip -qo /state/certs/elasticsearch.zip -d /state/certs
    fi
    cp /state/certs/ca/ca.crt /kibana-config/ca.crt
    cat > /kibana-config/kibana.yml <<EOF
server.name: stacksense-kibana
server.host: "0.0.0.0"
elasticsearch.hosts: ["https://elasticsearch:9200"]
elasticsearch.username: kibana_system
elasticsearch.password: "$(cat /state/kibana_password)"
elasticsearch.ssl.certificateAuthorities: ["/usr/share/kibana/config/ca.crt"]
elasticsearch.ssl.verificationMode: full
xpack.security.encryptionKey: "$(cat /state/security_key)"
xpack.reporting.encryptionKey: "$(cat /state/reporting_key)"
xpack.encryptedSavedObjects.encryptionKey: "$(cat /state/saved_objects_key)"
EOF
    chown -R 1000:0 /state /kibana-config
    find /state /kibana-config -type d -exec chmod 750 {} +
    find /state /kibana-config -type f -exec chmod 640 {} +
    echo "Local search certificates and persistent credentials are ready."
    ;;
  credentials)
    curl --silent --show-error --fail --max-time 10 \
      --retry 30 --retry-all-errors --retry-delay 2 --retry-max-time 180 \
      --cacert /state/certs/ca/ca.crt \
      --user "elastic:$(cat /state/elastic_password)" \
      --header 'Content-Type: application/json' --request POST \
      --data "{\"password\":\"$(cat /state/kibana_password)\"}" \
      --output /dev/null https://elasticsearch:9200/_security/user/kibana_system/_password
    echo "Kibana service credentials are configured."
    ;;
  *)
    echo "Expected certificates or credentials bootstrap step." >&2
    exit 2
    ;;
esac
