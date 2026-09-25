<?php
if (!defined('ABSPATH')) exit;

final class K20_Bridge_V32_Snapshots {
    private const CPT='k20_bridge_snapshot';
    private const LIMIT=120;

    public static function boot(): void {
        register_post_type(self::CPT,[
            'label'=>'K20 Bridge Snapshots','public'=>false,'show_ui'=>false,'show_in_rest'=>false,
            'supports'=>['title','editor','custom-fields'],'capability_type'=>'post','map_meta_cap'=>true
        ]);
    }

    public static function capture(string $kind,int $object_id,string $field,$value,array $meta=[]): int {
        $raw=is_string($value)?$value:wp_json_encode($value,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
        $encoded=base64_encode(gzencode($raw,6));
        $id=wp_insert_post([
            'post_type'=>self::CPT,'post_status'=>'private',
            'post_title'=>sprintf('%s:%d:%s:%s',$kind,$object_id,$field,gmdate('YmdHis')),
            'post_content'=>$encoded
        ],true);
        if (is_wp_error($id)) return 0;
        foreach ([
            '_k20_kind'=>$kind,'_k20_object_id'=>$object_id,'_k20_field'=>$field,
            '_k20_sha256'=>hash('sha256',$raw),'_k20_created_utc'=>gmdate('c'),
            '_k20_meta'=>wp_json_encode($meta,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES)
        ] as $k=>$v) update_post_meta($id,$k,$v);
        self::prune();
        return (int)$id;
    }

    public static function list(array $body): array {
        $p=is_array($body['payload']??null)?$body['payload']:[];
        $limit=max(1,min(50,(int)($p['limit']??20)));
        $args=['post_type'=>self::CPT,'post_status'=>'private','posts_per_page'=>$limit,'orderby'=>'ID','order'=>'DESC'];
        if (!empty($p['object_id'])) $args['meta_query']=[['key'=>'_k20_object_id','value'=>absint($p['object_id']),'compare'=>'=']];
        $rows=[];
        foreach (get_posts($args) as $post) {
            $rows[]=[
                'snapshot_id'=>$post->ID,'kind'=>get_post_meta($post->ID,'_k20_kind',true),
                'object_id'=>(int)get_post_meta($post->ID,'_k20_object_id',true),
                'field'=>get_post_meta($post->ID,'_k20_field',true),
                'sha256'=>get_post_meta($post->ID,'_k20_sha256',true),
                'created_at_utc'=>get_post_meta($post->ID,'_k20_created_utc',true)
            ];
        }
        return ['count'=>count($rows),'items'=>$rows];
    }

    public static function rollback(array $body,bool $dry_run) {
        $p=is_array($body['payload']??null)?$body['payload']:[];
        $sid=absint($p['snapshot_id']??0);
        $post=$sid?get_post($sid):null;
        if (!$post || $post->post_type!==self::CPT) return new WP_Error('snapshot_not_found','Snapshot not found.',['status'=>404]);
        $kind=(string)get_post_meta($sid,'_k20_kind',true);
        $object_id=(int)get_post_meta($sid,'_k20_object_id',true);
        $field=(string)get_post_meta($sid,'_k20_field',true);
        $raw=self::decode((string)$post->post_content);
        if (is_wp_error($raw)) return $raw;

        if ($dry_run) return ['planned'=>true,'snapshot_id'=>$sid,'kind'=>$kind,'object_id'=>$object_id,'field'=>$field,'sha256'=>hash('sha256',$raw)];

        if ($kind==='post_field') {
            $obj=get_post($object_id);
            if (!$obj) return new WP_Error('target_not_found','Snapshot target post not found.',['status'=>404]);
            $current=(string)$obj->{$field};
            self::capture('post_field',$object_id,$field,$current,['rollback_of'=>$sid]);
            $r=wp_update_post(['ID'=>$object_id,$field=>$raw],true);
            if (is_wp_error($r)) return $r;
        } elseif ($kind==='post_meta') {
            if (!get_post($object_id)) return new WP_Error('target_not_found','Snapshot target post not found.',['status'=>404]);
            $current=get_post_meta($object_id,$field,true);
            self::capture('post_meta',$object_id,$field,$current,['rollback_of'=>$sid]);
            update_post_meta($object_id,$field,wp_slash($raw));
        } elseif ($kind==='seo_meta') {
            $decoded=json_decode($raw,true);
            if (!is_array($decoded)) return new WP_Error('snapshot_corrupt','SEO snapshot is invalid.',['status'=>500]);
            foreach ($decoded as $k=>$v) update_post_meta($object_id,$k,$v);
        } elseif ($kind==='media_meta') {
            $decoded=json_decode($raw,true);
            if (!is_array($decoded)) return new WP_Error('snapshot_corrupt','Media snapshot is invalid.',['status'=>500]);
            if (isset($decoded['post'])) {
                $u=['ID'=>$object_id];
                foreach (['post_title','post_excerpt','post_content'] as $f) if (array_key_exists($f,$decoded['post'])) $u[$f]=$decoded['post'][$f];
                if (count($u)>1) wp_update_post($u);
            }
            if (array_key_exists('alt_text',$decoded)) update_post_meta($object_id,'_wp_attachment_image_alt',$decoded['alt_text']);
        } elseif ($kind==='snippet') {
            $decoded=json_decode($raw,true);
            if (!is_array($decoded)) return new WP_Error('snapshot_corrupt','Snippet snapshot is invalid.',['status'=>500]);
            $payload=[];
            foreach (['name','desc','code','tags','scope','priority','locked','trashed'] as $key) if (array_key_exists($key,$decoded)) $payload[$key]=$decoded[$key];
            $payload['active']=false;
            $payload['network']=false;
            $req=new WP_REST_Request('PUT','/code-snippets/v1/snippets/'.$object_id);
            $req->set_body_params($payload);
            $res=rest_do_request($req);
            if (is_wp_error($res)) return $res;
            $status=$res->get_status();
            if ($status<200 || $status>=300) return new WP_Error('snippet_rollback_failed','Snippet rollback request failed.',['status'=>$status]);
        } else {
            return new WP_Error('snapshot_kind_unsupported','Snapshot kind cannot be rolled back.',['status'=>400]);
        }

        self::clear_caches();
        return ['rolled_back'=>true,'snapshot_id'=>$sid,'kind'=>$kind,'object_id'=>$object_id,'field'=>$field];
    }

    private static function decode(string $encoded) {
        $bin=base64_decode($encoded,true);
        if ($bin===false) return new WP_Error('snapshot_corrupt','Snapshot payload is invalid.',['status'=>500]);
        $raw=@gzdecode($bin);
        if ($raw===false) return new WP_Error('snapshot_corrupt','Snapshot payload cannot be decoded.',['status'=>500]);
        return $raw;
    }

    private static function prune(): void {
        $ids=get_posts(['post_type'=>self::CPT,'post_status'=>'private','posts_per_page'=>-1,'fields'=>'ids','orderby'=>'ID','order'=>'DESC']);
        foreach (array_slice($ids,self::LIMIT) as $id) wp_delete_post($id,true);
    }

    private static function clear_caches(): void {
        if (class_exists('Elementor\\Plugin')) {
            try {
                $plugin=\Elementor\Plugin::instance();
                if (isset($plugin->files_manager) && method_exists($plugin->files_manager,'clear_cache')) $plugin->files_manager->clear_cache();
            } catch (Throwable $e) {}
        }
        if (function_exists('wp_cache_flush')) wp_cache_flush();
        if (defined('LSCWP_V') || has_action('litespeed_purge_all')) do_action('litespeed_purge_all');
    }
}
add_action('init',['K20_Bridge_V32_Snapshots','boot']);
