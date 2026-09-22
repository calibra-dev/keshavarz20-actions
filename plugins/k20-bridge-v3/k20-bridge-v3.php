<?php
/**
 * Plugin Name: Keshavarz20 Bridge v3
 * Description: GitHub-first guarded execution bridge for Keshavarz20.
 * Version: 3.1.0
 * Author: Keshavarz20
 */

if (!defined('ABSPATH')) exit;

require_once __DIR__.'/includes/class-k20-bridge-v31-content.php';
require_once __DIR__.'/includes/class-k20-bridge-v31-media.php';
require_once __DIR__.'/includes/class-k20-bridge-v31-jobs.php';

final class K20_Bridge_V3 {
    private const VERSION='3.1.0';
    private const NS='keshavarz20-ops/v3';
    private const AUDIT_OPTION='k20_bridge_v3_audit';
    private const AUDIT_LIMIT=300;
    private const RECEIPT_TTL=HOUR_IN_SECONDS;
    private const BATCH_MAX=30;

    private static array $blocked_keys=[
        'price','regular_price','sale_price','date_on_sale_from','date_on_sale_to',
        'discount','discount_type','coupon','coupon_code','payment_method','payment_method_title',
        'tax_status','tax_class','password','application_password','token','secret','api_key',
        'consumer_key','consumer_secret','role','roles','capability','capabilities','author',
        'user_id','customer_id','billing','shipping_address','email','phone','order_id','orders',
        'sql','query_sql','php','code','command','shell'
    ];

    public static function boot(): void { add_action('rest_api_init',[__CLASS__,'routes']); }

    public static function routes(): void {
        foreach (['/'=>'index','/health'=>'health','/capabilities'=>'capabilities_route'] as $route=>$method) {
            register_rest_route(self::NS,$route,['methods'=>'GET','callback'=>[__CLASS__,$method],'permission_callback'=>[__CLASS__,'can_read']]);
        }
        register_rest_route(self::NS,'/execute',['methods'=>'POST','callback'=>[__CLASS__,'execute'],'permission_callback'=>[__CLASS__,'can_write']]);
    }

    public static function can_read(): bool { return is_user_logged_in() && current_user_can('edit_posts'); }
    public static function can_write(): bool { return is_user_logged_in() && current_user_can('manage_options'); }

    public static function index(): WP_REST_Response {
        return self::response(['ok'=>true,'plugin'=>'Keshavarz20 Bridge v3','version'=>self::VERSION,'namespace'=>self::NS,'routes'=>['/','/health','/capabilities','/execute']]);
    }

    public static function health(): WP_REST_Response {
        return self::response([
            'ok'=>true,'status'=>'healthy','plugin'=>'Keshavarz20 Bridge v3','version'=>self::VERSION,
            'wp_version'=>get_bloginfo('version'),'php_version'=>PHP_VERSION,'https'=>is_ssl(),
            'woocommerce'=>class_exists('WooCommerce'),'yoast'=>defined('WPSEO_VERSION'),
            'elementor'=>defined('ELEMENTOR_VERSION'),'object_cache'=>wp_using_ext_object_cache(),
            'media_engine'=>class_exists('K20_Bridge_V31_Media'),
            'content_engine'=>class_exists('K20_Bridge_V31_Content'),
            'job_engine'=>class_exists('K20_Bridge_V31_Jobs'),
        ]);
    }

    public static function capabilities_route(): WP_REST_Response {
        return self::response([
            'ok'=>true,'version'=>self::VERSION,'actions'=>self::actions(),'rest_routes'=>self::route_patterns(),
            'methods'=>['GET','POST','PUT'],'supports_dry_run'=>true,'supports_idempotency'=>true,
            'batch_max'=>self::BATCH_MAX,'background_job_item_max'=>500,'audit_limit'=>self::AUDIT_LIMIT,
            'hard_denies'=>self::$blocked_keys,
            'github_side_actions'=>['engine.status','engine.run','gitops.profile'],
        ]);
    }

    private static function actions(): array {
        return [
            'system.info','rest.proxy','seo.read','seo.update',
            'content.search','content.patch',
            'elementor.inspect','elementor.search','elementor.edit',
            'media.import','media.transform','media.metadata',
            'cache.status','cache.purge','audit.tail','batch',
            'job.create','job.status','job.run'
        ];
    }

    private static function route_patterns(): array {
        return [
            '#^/wp/v2/posts(?:/\d+)?$#','#^/wp/v2/pages(?:/\d+)?$#','#^/wp/v2/media(?:/\d+)?$#',
            '#^/wp/v2/categories(?:/\d+)?$#','#^/wp/v2/tags(?:/\d+)?$#','#^/wp/v2/search$#',
            '#^/wc/v3/products(?:/\d+)?$#','#^/wc/v3/products/categories(?:/\d+)?$#',
            '#^/wc/v3/products/tags(?:/\d+)?$#','#^/wc/v3/products/attributes(?:/\d+)?(?:/terms(?:/\d+)?)?$#',
        ];
    }

    public static function execute(WP_REST_Request $request): WP_REST_Response {
        $body=$request->get_json_params();
        if (!is_array($body)) return self::error('invalid_json','JSON object required.',400);
        $action=self::action((string)($body['action'] ?? ''));
        if (!in_array($action,self::actions(),true)) return self::error('action_not_allowed','Action is not allow-listed.',400);
        if (($bad=self::blocked_path($body))!==null) return self::error('forbidden_key','Request contains a forbidden key.',400,['key'=>$bad]);
        $request_id=isset($body['request_id'])?substr(sanitize_text_field((string)$body['request_id']),0,80):'';
        $dry=!empty($body['dry_run']);
        if ($request_id!=='') {
            $cached=get_transient(self::receipt_key($request_id));
            if (is_array($cached)) { $cached['replayed']=true; return self::response($cached); }
        }
        try {
            $result=self::dispatch_for_job($action,$body,$dry);
            if (is_wp_error($result)) {
                $data=$result->get_error_data(); $status=is_array($data)&&isset($data['status'])?(int)$data['status']:400;
                self::audit($action,false,$dry,$request_id,$result->get_error_code());
                return self::error($result->get_error_code(),$result->get_error_message(),$status);
            }
            $envelope=['ok'=>true,'bridge'=>'Keshavarz20 Bridge v3','version'=>self::VERSION,'action'=>$action,'request_id'=>$request_id?:null,'dry_run'=>$dry,'executed_at_utc'=>gmdate('c'),'result'=>self::redact($result)];
            if ($request_id!=='') set_transient(self::receipt_key($request_id),$envelope,self::RECEIPT_TTL);
            self::audit($action,true,$dry,$request_id,'ok');
            return self::response($envelope);
        } catch (Throwable $e) {
            self::audit($action,false,$dry,$request_id,'exception');
            return self::error('exception','Bridge execution failed.',500);
        }
    }

    public static function dispatch_for_job(string $action,array $body,bool $dry) {
        if (!in_array($action,self::actions(),true)) return new WP_Error('action_not_allowed','Action is not allow-listed.',['status'=>400]);
        if (($bad=self::blocked_path($body))!==null) return new WP_Error('forbidden_key','Request contains a forbidden key: '.$bad,['status'=>400]);
        switch ($action) {
            case 'system.info': return self::system_info();
            case 'rest.proxy': return self::rest_proxy($body,$dry);
            case 'seo.read': return self::seo_read(absint($body['id'] ?? 0));
            case 'seo.update': return self::seo_update(absint($body['id'] ?? 0),(array)($body['payload'] ?? []),$dry);
            case 'content.search': return K20_Bridge_V31_Content::search($body);
            case 'content.patch': return K20_Bridge_V31_Content::patch($body,$dry);
            case 'elementor.inspect': return K20_Bridge_V31_Content::elementor_inspect(absint($body['id'] ?? 0));
            case 'elementor.search': return K20_Bridge_V31_Content::elementor_search($body);
            case 'elementor.edit': return K20_Bridge_V31_Content::elementor_edit($body,$dry);
            case 'media.import': return K20_Bridge_V31_Media::import_url($body,$dry);
            case 'media.transform': return K20_Bridge_V31_Media::transform($body,$dry);
            case 'media.metadata': return K20_Bridge_V31_Media::metadata($body,$dry);
            case 'cache.status': return self::cache_status();
            case 'cache.purge': return self::cache_purge($dry);
            case 'audit.tail': return self::audit_tail((array)($body['payload'] ?? []));
            case 'batch': return self::batch((array)($body['payload'] ?? []),$dry);
            case 'job.create': return K20_Bridge_V31_Jobs::create($body,$dry);
            case 'job.status': return K20_Bridge_V31_Jobs::status($body);
            case 'job.run': return K20_Bridge_V31_Jobs::run($body,$dry,[__CLASS__,'dispatch_for_job']);
        }
        return new WP_Error('not_implemented','Action is not implemented.',['status'=>501]);
    }

    private static function rest_proxy(array $body,bool $dry) {
        $method=strtoupper((string)($body['method'] ?? 'GET'));
        $path='/'.ltrim((string)($body['path'] ?? ''),'/');
        $query=is_array($body['query'] ?? null)?$body['query']:[];
        $payload=is_array($body['payload'] ?? null)?$body['payload']:[];
        if (!in_array($method,['GET','POST','PUT'],true)) return new WP_Error('method_not_allowed','Method is not allow-listed.',['status'=>405]);
        if (!self::route_allowed($path)) return new WP_Error('route_not_allowed','REST route is not allow-listed.',['status'=>403]);
        if (($bad=self::blocked_path(['query'=>$query,'payload'=>$payload]))!==null) return new WP_Error('forbidden_key','Request contains a forbidden key: '.$bad,['status'=>400]);
        if ($method!=='GET' && preg_match('#^/(?:wp/v2/(?:posts|pages)|wc/v3/products)$#',$path)) $payload['status']='draft';
        if ($method!=='GET' && $dry) return ['planned'=>true,'method'=>$method,'path'=>$path,'query'=>$query,'payload'=>self::redact($payload)];
        $req=new WP_REST_Request($method,$path);
        if ($query) $req->set_query_params($query);
        if ($payload) $req->set_body_params($payload);
        $res=rest_do_request($req);
        if (is_wp_error($res)) return $res;
        $status=$res->get_status(); $data=self::redact($res->get_data());
        if ($status<200 || $status>=300) return new WP_Error('upstream_rest_error',is_array($data)&&isset($data['message'])?(string)$data['message']:'Upstream REST request failed.',['status'=>$status]);
        return ['method'=>$method,'path'=>$path,'status'=>$status,'data'=>$data];
    }

    private static function route_allowed(string $path): bool { foreach (self::route_patterns() as $p) if (preg_match($p,$path)) return true; return false; }

    private static function system_info(): array {
        if (!function_exists('get_plugins')) require_once ABSPATH.'wp-admin/includes/plugin.php';
        $plugins=get_plugins(); $active=(array)get_option('active_plugins',[]); $rows=[];
        foreach ($active as $basename) { $p=$plugins[$basename] ?? []; $rows[]=['basename'=>$basename,'name'=>$p['Name'] ?? $basename,'version'=>$p['Version'] ?? null]; }
        $theme=wp_get_theme();
        return ['site_name'=>get_bloginfo('name'),'home_url'=>home_url('/'),'wp_version'=>get_bloginfo('version'),'php_version'=>PHP_VERSION,
            'theme'=>['name'=>$theme->get('Name'),'stylesheet'=>$theme->get_stylesheet(),'version'=>$theme->get('Version')],
            'active_plugins'=>$rows,'woocommerce'=>class_exists('WooCommerce'),'yoast'=>defined('WPSEO_VERSION')?WPSEO_VERSION:null,
            'elementor'=>defined('ELEMENTOR_VERSION')?ELEMENTOR_VERSION:null,'object_cache'=>wp_using_ext_object_cache()];
    }

    private static function seo_keys(): array { return ['title'=>'_yoast_wpseo_title','description'=>'_yoast_wpseo_metadesc','focus_keyword'=>'_yoast_wpseo_focuskw','canonical'=>'_yoast_wpseo_canonical','noindex'=>'_yoast_wpseo_meta-robots-noindex']; }
    private static function seo_read(int $id) {
        if (!$id || !get_post($id)) return new WP_Error('not_found','Post not found.',['status'=>404]);
        $out=['id'=>$id]; foreach (self::seo_keys() as $n=>$m) $out[$n]=get_post_meta($id,$m,true); return $out;
    }
    private static function seo_update(int $id,array $payload,bool $dry) {
        if (!$id || !get_post($id)) return new WP_Error('not_found','Post not found.',['status'=>404]);
        $changes=[]; foreach (self::seo_keys() as $n=>$m) if (array_key_exists($n,$payload)) $changes[$m]=$n==='noindex'?(!empty($payload[$n])?'1':'0'):sanitize_text_field((string)$payload[$n]);
        if (!$changes) return new WP_Error('no_fields','No allowed SEO fields supplied.',['status'=>400]);
        if ($dry) return ['planned'=>true,'id'=>$id,'changes'=>array_keys($changes)];
        foreach ($changes as $m=>$v) update_post_meta($id,$m,$v); return self::seo_read($id);
    }

    private static function cache_status(): array {
        return ['litespeed_active'=>defined('LSCWP_V'),'object_cache'=>wp_using_ext_object_cache(),'wp_cache_flush_available'=>function_exists('wp_cache_flush')];
    }
    private static function cache_purge(bool $dry): array {
        if ($dry) return ['planned'=>true,'targets'=>['litespeed','object_cache']];
        $actions=[]; if (defined('LSCWP_V') || has_action('litespeed_purge_all')) { do_action('litespeed_purge_all'); $actions[]='litespeed_purge_all'; }
        if (function_exists('wp_cache_flush')) { wp_cache_flush(); $actions[]='wp_cache_flush'; }
        return ['purged'=>true,'actions'=>$actions];
    }
    private static function audit_tail(array $payload): array {
        $limit=max(1,min(100,(int)($payload['limit'] ?? 20))); $rows=(array)get_option(self::AUDIT_OPTION,[]);
        return ['count'=>min(count($rows),$limit),'items'=>array_slice(array_reverse($rows),0,$limit)];
    }
    private static function batch(array $payload,bool $outer_dry) {
        $items=is_array($payload['items'] ?? null)?$payload['items']:[];
        if (!$items) return new WP_Error('batch_empty','payload.items is required.',['status'=>400]);
        if (count($items)>self::BATCH_MAX) return new WP_Error('batch_too_large','Batch exceeds limit.',['status'=>400]);
        $out=[];
        foreach ($items as $i=>$item) {
            if (!is_array($item)) { $out[]=['index'=>$i,'ok'=>false,'error'=>'invalid_item']; continue; }
            $action=self::action((string)($item['action'] ?? ''));
            if (in_array($action,['batch','job.create','job.run'],true) || !in_array($action,self::actions(),true)) { $out[]=['index'=>$i,'ok'=>false,'error'=>'action_not_allowed']; continue; }
            $r=self::dispatch_for_job($action,$item,$outer_dry || !empty($item['dry_run']));
            $out[]=is_wp_error($r)?['index'=>$i,'action'=>$action,'ok'=>false,'error'=>$r->get_error_code()]:['index'=>$i,'action'=>$action,'ok'=>true,'result'=>self::redact($r)];
        }
        return ['count'=>count($out),'items'=>$out];
    }

    private static function audit(string $action,bool $ok,bool $dry,string $request_id,string $status): void {
        $rows=(array)get_option(self::AUDIT_OPTION,[]); $rows[]=['at_utc'=>gmdate('c'),'action'=>$action,'ok'=>$ok,'dry_run'=>$dry,'request_id'=>$request_id?:null,'status'=>$status];
        if (count($rows)>self::AUDIT_LIMIT) $rows=array_slice($rows,-self::AUDIT_LIMIT); update_option(self::AUDIT_OPTION,$rows,false);
    }
    private static function blocked_path($value,string $path=''): ?string {
        if (!is_array($value)) return null;
        foreach ($value as $k=>$v) { $key=strtolower((string)$k); $full=$path===''?$key:$path.'.'.$key; if (in_array($key,self::$blocked_keys,true)) return $full; if (is_array($v) && ($f=self::blocked_path($v,$full))!==null) return $f; }
        return null;
    }
    private static function redact($value) {
        if (!is_array($value)) return $value; $out=[];
        foreach ($value as $k=>$v) { if (in_array(strtolower((string)$k),self::$blocked_keys,true)) continue; $out[$k]=is_array($v)?self::redact($v):$v; } return $out;
    }
    private static function action(string $v): string { $v=strtolower(trim($v)); return preg_replace('/[^a-z0-9._-]/','',$v) ?: ''; }
    private static function receipt_key(string $id): string { return 'k20b3_'.substr(hash('sha256',$id),0,32); }
    private static function response(array $data,int $status=200): WP_REST_Response { return new WP_REST_Response($data,$status); }
    private static function error(string $code,string $message,int $status,array $extra=[]): WP_REST_Response { return self::response(array_merge(['ok'=>false,'bridge'=>'Keshavarz20 Bridge v3','version'=>self::VERSION,'code'=>$code,'message'=>$message],$extra),$status); }
}
K20_Bridge_V3::boot();
