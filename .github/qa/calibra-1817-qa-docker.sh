#!/usr/bin/env bash
set -euo pipefail
mode="$1"
case "$mode" in legacy|hpos) ;; *) echo "Specify legacy or hpos"; exit 2;; esac
root="/tmp/calibra1817qa"
zip="$root/Calibra-Dashboard-1.8.17-VERIFIED-LIVE.zip"
fixture="$root/Calibra-Dashboard-1.8.16-VERSION-ONLY-FIXTURE.zip"
test -s "$zip" || { echo EXACT_INSTALLED_CODE_ZIP_MISSING; exit 1; }
test -s "$fixture" || { echo UPGRADE_FIXTURE_MISSING; exit 1; }
p="calibra1817-$mode-$GITHUB_RUN_ID"
network="$p-net"
volume="$p-wp"
db="$p-db"
web="$p-web"

cleanup() {
  code=$?
  if [ "$code" -ne 0 ]; then
    echo "DOCKER_FAILURE_LOGS mode=$mode"
    docker logs --tail 50 "$web" 2>/dev/null || true
    docker logs --tail 50 "$db" 2>/dev/null || true
  fi
  docker rm -f "$web" "$db" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network create "$network" >/dev/null
docker volume create "$volume" >/dev/null
docker run -d --name "$db" --network "$network" \
  -e MARIADB_ROOT_PASSWORD=disposable-only \
  -e MARIADB_DATABASE=wordpress \
  -e MARIADB_USER=wordpress \
  -e MARIADB_PASSWORD=wordpress \
  mariadb:10.11 >/dev/null
docker run -d --name "$web" --network "$network" \
  -v "$volume:/var/www/html" \
  -e "WORDPRESS_DB_HOST=$db:3306" \
  -e WORDPRESS_DB_NAME=wordpress \
  -e WORDPRESS_DB_USER=wordpress \
  -e WORDPRESS_DB_PASSWORD=wordpress \
  wordpress:php8.3-apache >/dev/null
for i in $(seq 1 90); do
  if docker exec "$db" mariadb-admin ping -u root -pdisposable-only --silent >/dev/null 2>&1; then break; fi
  sleep 2
done
for i in $(seq 1 90); do
  if docker exec "$web" test -f /var/www/html/wp-config.php; then break; fi
  sleep 2
done

wp() {
  docker run --rm --network "$network" \
    -v "$volume:/var/www/html" \
    -v "$root:/qa:ro" \
    --user 33:33 \
    -e "WORDPRESS_DB_HOST=$db:3306" \
    -e WORDPRESS_DB_NAME=wordpress \
    -e WORDPRESS_DB_USER=wordpress \
    -e WORDPRESS_DB_PASSWORD=wordpress \
    -e "CALIBRA_QA_MODE=$mode" \
    wordpress:cli-php8.3 wp "$@"
}

wp core install \
  --url="http://$web" --title="Calibra Docker QA" \
  --admin_user=qaadmin --admin_password=DisposableOnly123 \
  --admin_email=qa@example.test --skip-email
wp plugin install woocommerce --activate
wp plugin is-active woocommerce
if [ "$mode" = "hpos" ]; then
  wp option update woocommerce_custom_orders_table_enabled yes
else
  wp option update woocommerce_custom_orders_table_enabled no
fi
echo "WC_READY_MODE=$mode"

# Clean installation with the byte-verified live 1.8.17 source.
wp plugin install "/qa/$(basename "$zip")" --activate
wp plugin is-active k20-dashboard
test "$(wp plugin get k20-dashboard --field=version)" = 1.8.17
docker exec "$web" sh -c 'set -e; find /var/www/html/wp-content/plugins/k20-dashboard -type f -name "*.php" -exec php -l {} \; >/dev/null'
echo "FRESH_INSTALL_1817_OK mode=$mode"
wp eval-file /qa/calibra-1817-qa-smoke.php
wp option update calibra_qa_marker before_upgrade

# In-place forced replacement must keep activation and preserve orders.
wp plugin install "/qa/$(basename "$zip")" --force
wp plugin is-active k20-dashboard
test "$(wp plugin get k20-dashboard --field=version)" = 1.8.17
wp eval-file /qa/calibra-1817-qa-smoke.php
echo "SAME_VERSION_IN_PLACE_REINSTALL_OK mode=$mode"

# Version-header-only upgrade fixture, not the historical 1.8.16 distribution.
wp plugin install "/qa/$(basename "$fixture")" --force
wp plugin is-active k20-dashboard
test "$(wp plugin get k20-dashboard --field=version)" = 1.8.16
echo "VERSION_ONLY_1816_UPGRADE_FIXTURE_INSTALLED mode=$mode"
wp plugin install "/qa/$(basename "$zip")" --force
wp plugin is-active k20-dashboard
test "$(wp plugin get k20-dashboard --field=version)" = 1.8.17
test "$(wp option get calibra_qa_marker)" = before_upgrade
wp eval-file /qa/calibra-1817-qa-smoke.php
echo "SYNTHETIC_PREVIOUS_HEADER_UPGRADE_1817_OK mode=$mode"
echo "DOCKER_INSTALL_AND_UPGRADE_SMOKE_PASS mode=$mode"
