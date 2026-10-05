<?php
if (!defined('ABSPATH')) exit;

/**
 * Read-only, sanitized runtime inspection for K20 Factor.
 *
 * This class intentionally does not expose customer/order rows, payment
 * configuration, credentials, arbitrary REST routes, or write operations.
 */
final class K20_Bridge_V334_K20Factor {
    private const PLUGIN_BASENAME='k20-factor/k20-factor.php';
    private const REST_NS='/k20-factor/v1';

    public static function health() {
        $diag=self::get(self::REST_NS.'/diagnostics');
        if (is_wp_error($diag)) return $diag;

        $connectors=self::get(self::REST_NS.'/connectors');
        if (is_wp_error($connectors)) return $connectors;

        $bootstrap=self::get(self::REST_NS.'/bootstrap');
        if (is_wp_error($bootstrap)) return $bootstrap;

        $diag_data=is_array($diag['data']??null)?$diag['data']:[];
        $conn_data=is_array($connectors['data']??null)?$connectors['data']:[];
        $boot_data=is_array($bootstrap['data']??null)?$bootstrap['data']:[];

        return [
            'active'=>self::active(),
            'installed_version'=>self::plugin_version(),
            'rest_version'=>isset($boot_data['version'])?sanitize_text_field((string)$boot_data['version']):null,
            'diagnostics'=>self::safe_diagnostics($diag_data),
            'providers'=>self::safe_providers($conn_data),
            'site'=>[
                'currency'=>isset($boot_data['site']['currency'])?sanitize_text_field((string)$boot_data['site']['currency']):null,
                'currency_symbol'=>isset($boot_data['site']['currency_symbol'])?sanitize_text_field((string)$boot_data['site']['currency_symbol']):null,
                'price_decimals'=>isset($boot_data['site']['price_decimals'])?(int)$boot_data['site']['price_decimals']:null,
            ],
            'rest_status'=>[
                'bootstrap'=>(int)($bootstrap['status']??0),
                'diagnostics'=>(int)($diag['status']??0),
                'connectors'=>(int)($connectors['status']??0),
            ],
        ];
    }

    public static function smoke() {
        $checks=[];

        $targets=[
            'bootstrap'=>[self::REST_NS.'/bootstrap',[]],
            'diagnostics'=>[self::REST_NS.'/diagnostics',[]],
            'connectors'=>[self::REST_NS.'/connectors',[]],
            'documents'=>[self::REST_NS.'/documents',['per_page'=>1,'page'=>1]],
            'reports'=>[self::REST_NS.'/reports',['days'=>30]],
            'products'=>[self::REST_NS.'/products',['search'=>'__k20_bridge_smoke_no_match_334__','limit'=>1]],
            'customers'=>[self::REST_NS.'/customers',['search'=>'__k20_bridge_smoke_no_match_334__']],
        ];

        foreach ($targets as $name=>$spec) {
            $r=self::get($spec[0],$spec[1]);
            if (is_wp_error($r)) {
                $checks[$name]=['ok'=>false,'code'=>$r->get_error_code()];
                continue;
            }
            $data=is_array($r['data']??null)?$r['data']:[];
            $checks[$name]=[
                'ok'=>(int)$r['status']>=200 && (int)$r['status']<300,
                'status'=>(int)$r['status'],
                'shape'=>array_values(array_slice(array_keys($data),0,40)),
            ];
            if ($name==='bootstrap') {
                $checks[$name]['version']=isset($data['version'])?sanitize_text_field((string)$data['version']):null;
            }
            if (in_array($name,['products','customers'],true)) {
                $checks[$name]['empty_probe']=isset($data['items']) && is_array($data['items']) && count($data['items'])===0;
            }
            if ($name==='documents') {
                $checks[$name]['items_array']=isset($data['items']) && is_array($data['items']);
            }
        }

        $ok=true;
        foreach ($checks as $row) {
            if (empty($row['ok'])) { $ok=false; break; }
        }

        return [
            'ok'=>$ok,
            'plugin_version'=>self::plugin_version(),
            'checks'=>$checks,
            'privacy_note'=>'Only status/shape metadata is returned; document, customer, payment and credential values are not exposed.',
        ];
    }

    public static function assets() {
        $base=trailingslashit(WP_PLUGIN_DIR).'k20-factor';
        $files=[
            'k20-factor.php',
            'assets/css/admin.css',
            'assets/css/public.css',
            'assets/js/admin.js',
            'assets/js/public.js',
        ];
        $out=[];
        foreach ($files as $rel) {
            $full=$base.'/'.$rel;
            $out[]=[
                'path'=>$rel,
                'exists'=>is_file($full),
                'bytes'=>is_file($full)?(int)filesize($full):null,
                'sha256'=>is_file($full)?hash_file('sha256',$full):null,
            ];
        }
        return [
            'active'=>self::active(),
            'plugin_version'=>self::plugin_version(),
            'files'=>$out,
        ];
    }

    private static function get(string $path,array $query=[]) {
        $req=new WP_REST_Request('GET',$path);
        if ($query) $req->set_query_params($query);
        $res=rest_do_request($req);
        if (is_wp_error($res)) return $res;
        $status=(int)$res->get_status();
        if ($status<200 || $status>=300) {
            return new WP_Error('k20factor_rest_failed','K20 Factor read-only smoke request failed.',['status'=>$status,'path'=>$path]);
        }
        return ['status'=>$status,'data'=>$res->get_data()];
    }

    private static function safe_diagnostics(array $data): array {
        $keys=[
            'plugin_version','wordpress_version','wordpress_minimum_met','php_version','php_minimum_met',
            'php_recommended_83_or_newer','woocommerce_version','woocommerce_minimum_met',
            'stock_reservation_api','stock_management_enabled','stock_hold_minutes','hpos_enabled',
            'action_scheduler','wp_cron_disabled','next_expiry_sweep','crypto_backend','crypto_ready',
            'pdf_storage_writable','pdf_storage_outside_webroot','pdf_storage_mode','https',
            'provider_webhooks_https','rest_url'
        ];
        $out=[];
        foreach ($keys as $key) if (array_key_exists($key,$data)) $out[$key]=$data[$key];
        return $out;
    }

    private static function safe_providers(array $data): array {
        $out=[
            'sms_plugins_detected'=>self::plugin_rows($data['sms_plugins_detected']??[]),
            'whatsapp_plugins_detected'=>self::plugin_rows($data['whatsapp_plugins_detected']??[]),
            'sms_direct'=>self::bool_map($data['sms_direct']??[]),
            'whatsapp_direct'=>self::bool_map($data['whatsapp_direct']??[]),
            'pwsms_adapter_connected'=>!empty($data['pwsms_adapter_connected']),
            'wsms_adapter_connected'=>!empty($data['wsms_adapter_connected']),
            'external_sms_filter_connected'=>!empty($data['external_sms_filter_connected']),
            'external_whatsapp_filter_connected'=>!empty($data['external_whatsapp_filter_connected']),
        ];
        if (isset($data['pwsms']) && is_array($data['pwsms'])) {
            $out['pwsms']=[
                'available'=>!empty($data['pwsms']['available']),
                'ready'=>!empty($data['pwsms']['ready']),
                'gateway'=>isset($data['pwsms']['gateway'])?sanitize_text_field((string)$data['pwsms']['gateway']):null,
                'gateway_class'=>isset($data['pwsms']['gateway_class'])?sanitize_text_field((string)$data['pwsms']['gateway_class']):null,
            ];
        }
        return $out;
    }

    private static function plugin_rows($rows): array {
        if (!is_array($rows)) return [];
        $out=[];
        foreach (array_slice($rows,0,20) as $row) {
            if (!is_array($row)) continue;
            $out[]=[
                'name'=>isset($row['name'])?sanitize_text_field((string)$row['name']):null,
                'version'=>isset($row['version'])?sanitize_text_field((string)$row['version']):null,
            ];
        }
        return $out;
    }

    private static function bool_map($row): array {
        if (!is_array($row)) return [];
        $out=[];
        foreach ($row as $key=>$value) {
            $clean=sanitize_key((string)$key);
            if ($clean!=='') $out[$clean]=(bool)$value;
        }
        return $out;
    }

    private static function active(): bool {
        if (!function_exists('is_plugin_active')) require_once ABSPATH.'wp-admin/includes/plugin.php';
        return is_plugin_active(self::PLUGIN_BASENAME);
    }

    private static function plugin_version(): ?string {
        if (!function_exists('get_plugin_data')) require_once ABSPATH.'wp-admin/includes/plugin.php';
        $file=trailingslashit(WP_PLUGIN_DIR).self::PLUGIN_BASENAME;
        if (!is_file($file)) return null;
        $data=get_plugin_data($file,false,false);
        return isset($data['Version'])?sanitize_text_field((string)$data['Version']):null;
    }
}
