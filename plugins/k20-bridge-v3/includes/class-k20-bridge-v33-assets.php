<?php
if (!defined('ABSPATH')) exit;

final class K20_Bridge_V33_Assets {
    private const MAX_BYTES = 20971520;
    private static array $allowed_mimes = ['image/jpeg','image/png','image/webp'];

    public static function upload_route(WP_REST_Request $request): WP_REST_Response {
        $files=$request->get_file_params();
        $file=is_array($files['file']??null)?$files['file']:null;
        if (!$file) return self::error('file_required','Multipart field "file" is required.',400);
        $err=(int)($file['error']??UPLOAD_ERR_OK);
        if ($err!==UPLOAD_ERR_OK) return self::error('upload_failed','Upload did not complete successfully.',400,['upload_error'=>$err]);
        $tmp=(string)($file['tmp_name']??'');
        $size=(int)($file['size']??0);
        if (!$tmp || !is_file($tmp)) return self::error('upload_missing','Uploaded temporary file is missing.',400);
        if ($size<1 || $size>self::MAX_BYTES) return self::error('media_too_large','Image must be between 1 byte and 20 MiB.',400);

        require_once ABSPATH.'wp-admin/includes/file.php';
        require_once ABSPATH.'wp-admin/includes/media.php';
        require_once ABSPATH.'wp-admin/includes/image.php';

        $original_name=sanitize_file_name((string)($file['name']??'k20-chat-image'));
        $type=wp_check_filetype_and_ext($tmp,$original_name);
        $source_mime=(string)($type['type']??'');
        $source_ext=(string)($type['ext']??'');
        if (!in_array($source_mime,self::$allowed_mimes,true) || !$source_ext) {
            return self::error('mime_not_allowed','Only JPEG, PNG and WebP images are allowed.',400);
        }

        $params=$request->get_params();
        $target_mime=sanitize_mime_type((string)($params['output_mime']??$source_mime));
        if (!in_array($target_mime,self::$allowed_mimes,true)) {
            return self::error('mime_not_allowed','Requested output mime is not allowed.',400);
        }
        $quality=max(40,min(95,(int)($params['quality']??88)));
        $max_dimension=max(256,min(4096,(int)($params['max_dimension']??1920)));
        $post_id=absint($params['post_id']??0);
        if ($post_id && !get_post($post_id)) return self::error('target_not_found','post_id does not exist.',404);

        $generated='';
        try {
            $editor=wp_get_image_editor($tmp);
            if (is_wp_error($editor)) return self::wp_error($editor);
            $dimensions=$editor->get_size();
            $w=(int)($dimensions['width']??0);
            $h=(int)($dimensions['height']??0);
            if (max($w,$h)>$max_dimension) {
                if ($w >= $h) { $nw=$max_dimension; $nh=max(1,(int)round($h*$max_dimension/$w)); }
                else { $nh=$max_dimension; $nw=max(1,(int)round($w*$max_dimension/$h)); }
                $r=$editor->resize($nw,$nh,false);
                if (is_wp_error($r)) return self::wp_error($r);
            }
            $editor->set_quality($quality);
            $ext=self::extension_for_mime($target_mime);
            $generated=trailingslashit(dirname($tmp)).'k20-v33-'.wp_generate_uuid4().'.'.$ext;
            $saved=$editor->save($generated,$target_mime);
            if (is_wp_error($saved)) return self::wp_error($saved);
            $work=(string)$saved['path'];

            $requested=sanitize_file_name((string)($params['filename']??$original_name));
            $base=pathinfo($requested,PATHINFO_FILENAME);
            if ($base==='') $base='k20-chat-'.gmdate('Ymd-His');
            $name=$base.'.'.$ext;
            $sideload=['name'=>$name,'tmp_name'=>$work,'error'=>UPLOAD_ERR_OK,'size'=>filesize($work)];
            $title=sanitize_text_field((string)($params['title']??$base));
            $id=media_handle_sideload($sideload,$post_id,$title);
            if (is_wp_error($id)) return self::wp_error($id);
            $generated='';

            if (array_key_exists('alt_text',$params)) update_post_meta($id,'_wp_attachment_image_alt',sanitize_text_field((string)$params['alt_text']));
            if (array_key_exists('caption',$params)) wp_update_post(['ID'=>$id,'post_excerpt'=>wp_kses_post((string)$params['caption'])]);
            $path=get_attached_file($id);
            $sha=$path&&is_file($path)?hash_file('sha256',$path):null;
            if ($sha) update_post_meta($id,'_k20_file_sha256',$sha);
            $meta=wp_get_attachment_metadata($id);

            return new WP_REST_Response([
                'ok'=>true,'bridge'=>'Keshavarz20 Bridge v3',
                'version'=>defined('K20_BRIDGE_RUNTIME_VERSION')?K20_BRIDGE_RUNTIME_VERSION:'3.3.0',
                'contract'=>'3.3',
                'result'=>[
                    'attachment_id'=>(int)$id,'url'=>wp_get_attachment_url($id),
                    'mime'=>get_post_mime_type($id),'bytes'=>$path&&is_file($path)?filesize($path):null,
                    'sha256'=>$sha,'width'=>$meta['width']??null,'height'=>$meta['height']??null,
                    'alt_text'=>get_post_meta($id,'_wp_attachment_image_alt',true)
                ]
            ],201);
        } finally {
            if ($generated && is_file($generated)) @unlink($generated);
        }
    }

    public static function featured_set(array $body,bool $dry_run) {
        $p=self::payload($body);
        $target_id=absint($p['target_id']??($p['post_id']??0));
        $attachment_id=absint($p['attachment_id']??0);
        $target=$target_id?get_post($target_id):null;
        if (!$target) return new WP_Error('target_not_found','Target post/product was not found.',['status'=>404]);
        if (!self::is_image($attachment_id)) return new WP_Error('attachment_not_found','Image attachment was not found.',['status'=>404]);
        $before=(int)get_post_thumbnail_id($target_id);
        if ($dry_run) return ['planned'=>true,'target_id'=>$target_id,'attachment_id'=>$attachment_id,'previous_attachment_id'=>$before];
        $snapshot=K20_Bridge_V32_Snapshots::capture('post_meta',$target_id,'_thumbnail_id',(string)$before,['action'=>'asset.featured.set']);
        if (!set_post_thumbnail($target_id,$attachment_id)) return new WP_Error('featured_set_failed','Could not set featured image.',['status'=>500]);
        self::clear_target_cache($target_id);
        return ['target_id'=>$target_id,'featured_attachment_id'=>$attachment_id,'previous_attachment_id'=>$before,'snapshot_id'=>$snapshot];
    }

    public static function gallery_append(array $body,bool $dry_run) {
        return self::gallery_write($body,$dry_run,false);
    }

    public static function gallery_replace(array $body,bool $dry_run) {
        return self::gallery_write($body,$dry_run,true);
    }

    private static function gallery_write(array $body,bool $dry_run,bool $replace) {
        if (!function_exists('wc_get_product')) return new WP_Error('woocommerce_required','WooCommerce is required.',['status'=>501]);
        $p=self::payload($body);
        $product_id=absint($p['product_id']??($p['target_id']??0));
        $product=$product_id?wc_get_product($product_id):false;
        if (!$product) return new WP_Error('product_not_found','Product was not found.',['status'=>404]);
        $ids=self::attachment_ids($p);
        if (!$ids) return new WP_Error('attachment_ids_required','At least one attachment_id is required.',['status'=>400]);
        foreach ($ids as $id) if (!self::is_image($id)) return new WP_Error('attachment_not_found','One or more image attachments were not found.',['status'=>404,'attachment_id'=>$id]);
        $before=array_values(array_map('intval',$product->get_gallery_image_ids()));
        $featured=(int)$product->get_image_id();
        $ids=array_values(array_filter($ids,fn($id)=>$id!==$featured));
        $after=$replace?array_values(array_unique($ids)):array_values(array_unique(array_merge($before,$ids)));
        if ($dry_run) return ['planned'=>true,'product_id'=>$product_id,'mode'=>$replace?'replace':'append','before_gallery_image_ids'=>$before,'gallery_image_ids'=>$after,'featured_attachment_id'=>$featured];
        $snapshot=K20_Bridge_V32_Snapshots::capture('post_meta',$product_id,'_product_image_gallery',implode(',',$before),['action'=>$replace?'asset.gallery.replace':'asset.gallery.append']);
        $product->set_gallery_image_ids($after);
        $product->save();
        self::clear_target_cache($product_id);
        $read=wc_get_product($product_id);
        $final=$read?array_values(array_map('intval',$read->get_gallery_image_ids())):[];
        return ['product_id'=>$product_id,'mode'=>$replace?'replace':'append','before_gallery_image_ids'=>$before,'gallery_image_ids'=>$final,'featured_attachment_id'=>(int)($read?$read->get_image_id():$featured),'snapshot_id'=>$snapshot];
    }

    public static function content_insert(array $body,bool $dry_run) {
        $p=self::payload($body);
        $target_id=absint($p['target_id']??($p['post_id']??0));
        $post=$target_id?get_post($target_id):null;
        if (!$post) return new WP_Error('target_not_found','Target post/product was not found.',['status'=>404]);
        $ids=self::attachment_ids($p);
        if (!$ids) return new WP_Error('attachment_ids_required','At least one attachment_id is required.',['status'=>400]);
        foreach ($ids as $id) if (!self::is_image($id)) return new WP_Error('attachment_not_found','One or more image attachments were not found.',['status'=>404,'attachment_id'=>$id]);

        $before=(string)$post->post_content;
        $before_sha=hash('sha256',$before);
        $expected=strtolower((string)($p['expected_sha256']??''));
        if ($expected!=='' && !hash_equals($before_sha,$expected)) return new WP_Error('stale_content','Content SHA-256 no longer matches expected value.',['status'=>409,'current_sha256'=>$before_sha]);

        $blocks=[];
        foreach ($ids as $id) {
            $url=wp_get_attachment_image_url($id,'full');
            if (!$url) continue;
            $alt=esc_attr((string)get_post_meta($id,'_wp_attachment_image_alt',true));
            $blocks[]='<!-- wp:image {"id":'.$id.',"sizeSlug":"full","linkDestination":"none"} -->'."\n".
                '<figure class="wp-block-image size-full"><img src="'.esc_url($url).'" alt="'.$alt.'" class="wp-image-'.$id.'"/></figure>'."\n".
                '<!-- /wp:image -->';
        }
        if (!$blocks) return new WP_Error('image_block_failed','Could not build image blocks.',['status'=>500]);
        $insert=implode("\n\n",$blocks);
        $position=(string)($p['position']??'append');
        if (!in_array($position,['append','prepend','after_text'],true)) return new WP_Error('position_not_allowed','position must be append, prepend or after_text.',['status'=>400]);
        if ($position==='prepend') $after=$insert."\n\n".$before;
        elseif ($position==='after_text') {
            $anchor=(string)($p['after_text']??'');
            if ($anchor==='') return new WP_Error('anchor_required','after_text is required for after_text position.',['status'=>400]);
            if (substr_count($before,$anchor)!==1) return new WP_Error('anchor_match_count','after_text must match exactly once.',['status'=>409]);
            $after=str_replace($anchor,$anchor."\n\n".$insert,$before);
        } else $after=rtrim($before)."\n\n".$insert;

        if ($dry_run) return ['planned'=>true,'target_id'=>$target_id,'attachment_ids'=>$ids,'position'=>$position,'before_sha256'=>$before_sha,'after_sha256'=>hash('sha256',$after)];
        $snapshot=K20_Bridge_V32_Snapshots::capture('post_field',$target_id,'post_content',$before,['action'=>'asset.content.insert']);
        $r=wp_update_post(['ID'=>$target_id,'post_content'=>wp_slash($after)],true);
        if (is_wp_error($r)) return $r;
        self::clear_target_cache($target_id);
        return ['target_id'=>$target_id,'attachment_ids'=>$ids,'position'=>$position,'snapshot_id'=>$snapshot,'before_sha256'=>$before_sha,'after_sha256'=>hash('sha256',(string)get_post_field('post_content',$target_id))];
    }

    private static function payload(array $body): array { return is_array($body['payload']??null)?$body['payload']:[]; }

    private static function attachment_ids(array $p): array {
        $ids=[];
        if (isset($p['attachment_id'])) $ids[]=(int)$p['attachment_id'];
        if (is_array($p['attachment_ids']??null)) foreach ($p['attachment_ids'] as $id) $ids[]=(int)$id;
        return array_values(array_unique(array_filter(array_map('absint',$ids))));
    }

    private static function is_image(int $id): bool {
        return $id>0 && get_post_type($id)==='attachment' && str_starts_with((string)get_post_mime_type($id),'image/');
    }

    private static function extension_for_mime(string $mime): string {
        if ($mime==='image/webp') return 'webp';
        if ($mime==='image/png') return 'png';
        return 'jpg';
    }

    private static function clear_target_cache(int $id): void {
        clean_post_cache($id);
        if (function_exists('wc_delete_product_transients') && get_post_type($id)==='product') wc_delete_product_transients($id);
        if (function_exists('wp_cache_flush')) wp_cache_flush();
        if (defined('LSCWP_V') || has_action('litespeed_purge_all')) do_action('litespeed_purge_all');
    }

    private static function wp_error(WP_Error $e): WP_REST_Response {
        $data=$e->get_error_data();
        $status=is_array($data)&&isset($data['status'])?(int)$data['status']:400;
        return self::error($e->get_error_code(),$e->get_error_message(),$status);
    }

    private static function error(string $code,string $message,int $status,array $extra=[]): WP_REST_Response {
        return new WP_REST_Response(array_merge([
            'ok'=>false,'bridge'=>'Keshavarz20 Bridge v3',
            'version'=>defined('K20_BRIDGE_RUNTIME_VERSION')?K20_BRIDGE_RUNTIME_VERSION:'3.3.0',
            'contract'=>'3.3','code'=>$code,'message'=>$message
        ],$extra),$status);
    }
}
