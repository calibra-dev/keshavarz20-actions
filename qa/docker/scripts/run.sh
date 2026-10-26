#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_RUN_ID:=}"
: "${QA_KEEP_VOLUMES:=0}"
: "${QA_ENABLE_BROWSER:=1}"

mode="$1"
case "$mode" in
  legacy|hpos) ;;
  *) echo "Usage: run.sh legacy|hpos" >&2; exit 2 ;;
esac

qa_dir="$(cd "$(dirname "$0")/.." && pwd)"
run_label="$mode"
project="k20qa-$run_label"
if [ -n "$GITHUB_RUN_ID" ]; then
  project="$project-$GITHUB_RUN_ID"
fi

compose() {
  docker compose --project-name "$project" --file "$qa_dir/compose.yml" "$@"
}
wp() {
  compose --profile cli run --rm -T -e "QA_STORAGE_MODE=$mode" wpcli wp "$@"
}
cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    echo "QA_FAILURE_CONTAINER_LOGS mode=$mode"
    compose logs --tail=60 database wordpress 2>/dev/null || true
  fi
  if [ "$QA_KEEP_VOLUMES" != "1" ]; then
    compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    echo "QA_EPHEMERAL_VOLUMES_CLEANED mode=$mode"
  fi
  exit "$status"
}

trap cleanup EXIT

mkdir -p "$qa_dir/fixtures" "$qa_dir/artifacts"
if [ -s "$qa_dir/fixtures/previous-plugin.zip" ] && [ ! -s "$qa_dir/fixtures/plugin-under-test.zip" ]; then
  echo "QA_OLD_PLUGIN_WITHOUT_NEW_PLUGIN" >&2
  exit 2
fi

compose up -d database wordpress
for _ in $(seq 1 90); do
  if compose exec -T wordpress test -f /var/www/html/wp-config.php >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
compose exec -T wordpress test -f /var/www/html/wp-config.php
compose exec -T wordpress php -l /var/www/html/wp-config.php

wp core install --url=http://wordpress --title="K20 Disposable QA" \
  --admin_user=qa-admin --admin_password=QaDisposableOnly123 \
  --admin_email=qa@example.test --skip-email

wp plugin install woocommerce --activate
wp plugin is-active woocommerce
if [ "$mode" = "hpos" ]; then
  wp option update woocommerce_custom_orders_table_enabled yes
else
  wp option update woocommerce_custom_orders_table_enabled no
fi
wp eval-file /qa/scripts/verify-environment.php
echo "QA_WP_WOO_BOOT_OK mode=$mode"

if [ -s "$qa_dir/fixtures/plugin-under-test.zip" ]; then
  wp plugin install /qa/fixtures/plugin-under-test.zip --activate
  wp eval-file /qa/scripts/verify-environment.php
  echo "QA_PLUGIN_FRESH_INSTALL_OK mode=$mode"

  # WordPress ZIP replacement of the exact same version.
  wp plugin install /qa/fixtures/plugin-under-test.zip --force
  wp eval-file /qa/scripts/verify-environment.php
  echo "QA_PLUGIN_REINSTALL_OK mode=$mode"

  if [ -s "$qa_dir/fixtures/previous-plugin.zip" ]; then
    wp plugin install /qa/fixtures/previous-plugin.zip --force
    wp eval-file /qa/scripts/verify-environment.php
    echo "QA_PREVIOUS_RELEASE_INSTALLED mode=$mode"
    wp plugin install /qa/fixtures/plugin-under-test.zip --force
    wp eval-file /qa/scripts/verify-environment.php
    echo "QA_GENUINE_UPGRADE_OK mode=$mode"
  fi
else
  echo "QA_PLUGIN_ZIP_NOT_PROVIDED_BASELINE_ONLY mode=$mode"
fi

if [ "$QA_ENABLE_BROWSER" = "1" ]; then
  compose --profile browser run --rm -T -e "QA_STORAGE_MODE=$mode" toolbox \
    node /qa/scripts/browser-smoke.cjs
  if [ -s "$qa_dir/fixtures/plugin-under-test.zip" ]; then
    compose --profile browser run --rm -T -e "QA_STORAGE_MODE=$mode" toolbox node /qa/scripts/calibra-map-visual.cjs
    echo "QA_CALIBRA_MAP_VISUAL_PASS mode=$mode"
  else
    echo "QA_CALIBRA_MAP_VISUAL_NOT_RUN_NO_PLUGIN mode=$mode"
  fi
  echo "QA_BROWSER_PASS mode=$mode"
fi

echo "QA_COMPLETE_PASS mode=$mode"
