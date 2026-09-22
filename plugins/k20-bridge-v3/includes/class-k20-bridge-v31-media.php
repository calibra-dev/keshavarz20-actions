<?php
if (!defined('ABSPATH')) exit;

final class K20_Bridge_V31_Media {
    private const MAX_BYTES = 15728640; // 15 MiB
    private static array $allowed_mimes = ['image/jpeg','image/png','image/webp'];

    public static function import_url(array $body, bool $dry_run) {
        $p = is_array($body['payload'] ?? null) ? $body['payload'] : [];
        $url = esc_url_raw((string)($p['url'] ?? ''));
        if (!$url || stripos($url, 'https://') !== 0) return new WP_Error('invalid_url','Only HTTPS media URLs are allowed.',['status'=>400]);
        $host = wp_parse_url($url, PHP_URL_HOST);
        if (!$host) return new WP_Error('invalid_host','Media URL host is invalid.',['status'=>400]);
        if ($dry_run) return ['planned'=>true,'url_host'=>$host];

        require_once ABSPATH.'wp-admin/includes/file.php';
        require_once ABSPATH.'wp-admin/includes/media.php';
        require_once ABSPATH.'wp-admin/includes/image.php';

        $tmp = download_url($url, 30);
        if (is_wp_error($tmp)) return $tmp;
        try {
            if (!file_exists($tmp) || filesize($tmp) > self::MAX_BYTES) return new WP_Error('media_too_large','Remote image exceeds 15 MiB.',['status'=>400]);
            $type = wp_check_filetype_and_ext($tmp, basename((string)wp_parse_url($url, PHP_URL_PATH)));
            $mime = $type['type'] ?? '';
            $ext = $type['ext'] ?? '';
            if (!in_array($mime, self::$allowed_mimes, true) || !$ext) return new WP_Error('mime_not_allowed','Only JPEG, PNG and WebP images are allowed.',['status'=>400]);
            $name = sanitize_file_name((string)($p['filename'] ?? ('k20-import-'.gmdate('Ymd-His').'.'.$ext)));
            if (!preg_match('/\.'.preg_quote($ext,'/').'$/i',$name)) $name .= '.'.$ext;
            $file = ['name'=>$name,'tmp_name'=>$tmp];
            $id = media_handle_sideload($file, absint($p['post_id'] ?? 0), sanitize_text_field((string)($p['title'] ?? '')));
            if (is_wp_error($id)) return $id;
            $tmp = null;
            if (isset($p['alt_text'])) update_post_meta($id,'_wp_attachment_image_alt',sanitize_text_field((string)$p['alt_text']));
            if (isset($p['caption'])) wp_update_post(['ID'=>$id,'post_excerpt'=>wp_kses_post((string)$p['caption'])]);
            return self::read($id);
        } finally {
            if ($tmp && file_exists($tmp)) @unlink($tmp);
        }
    }

    public static function transform(array $body, bool $dry_run) {
        $p = is_array($body['payload'] ?? null) ? $body['payload'] : [];
        $id = absint($p['attachment_id'] ?? ($body['id'] ?? 0));
        $src = $id ? get_attached_file($id) : '';
        if (!$id || !$src || !file_exists($src)) return new WP_Error('attachment_not_found','Image attachment not found.',['status'=>404]);
        $mime = get_post_mime_type($id);
        if (!in_array($mime,self::$allowed_mimes,true)) return new WP_Error('mime_not_allowed','Attachment is not a supported image.',['status'=>400]);

        $ops = [
            'resize'=>isset($p['width']) || isset($p['height']),
            'crop'=>isset($p['crop']),
            'rotate'=>isset($p['rotate']) ? (int)$p['rotate'] : 0,
            'flip_h'=>!empty($p['flip_h']),
            'flip_v'=>!empty($p['flip_v']),
            'quality'=>isset($p['quality']) ? max(40,min(95,(int)$p['quality'])) : null,
        ];
        if ($dry_run) return ['planned'=>true,'attachment_id'=>$id,'operations'=>$ops];

        require_once ABSPATH.'wp-admin/includes/image.php';
        $editor = wp_get_image_editor($src);
        if (is_wp_error($editor)) return $editor;
        if ($ops['quality'] !== null) $editor->set_quality($ops['quality']);
        $size = $editor->get_size();
        if ($ops['resize']) {
            $w = max(1, min(6000, (int)($p['width'] ?? $size['width'])));
            $h = max(1, min(6000, (int)($p['height'] ?? $size['height'])));
            $r = $editor->resize($w,$h,!empty($p['crop']));
            if (is_wp_error($r)) return $r;
        }
        if ($ops['rotate']) {
            $deg = $ops['rotate'];
            if (!in_array($deg,[90,180,270,-90,-180,-270],true)) return new WP_Error('invalid_rotate','rotate must be 90/180/270 degrees.',['status'=>400]);
            $r=$editor->rotate($deg); if (is_wp_error($r)) return $r;
        }
        if ($ops['flip_h'] || $ops['flip_v']) {
            $r=$editor->flip($ops['flip_h'],$ops['flip_v']); if (is_wp_error($r)) return $r;
        }

        $dir = dirname($src);
        $base = pathinfo($src,PATHINFO_FILENAME);
        $ext = pathinfo($src,PATHINFO_EXTENSION);
        $dest = wp_unique_filename($dir, $base.'-k20-'.gmdate('YmdHis').'.'.$ext);
        $saved = $editor->save($dir.'/'.$dest);
        if (is_wp_error($saved)) return $saved;

        $upload = wp_upload_dir();
        $file_abs = $saved['path'];
        $file_rel = ltrim(str_replace(trailingslashit($upload['basedir']),'',$file_abs),'/');
        $new_id = wp_insert_attachment([
            'post_mime_type'=>$saved['mime-type'] ?? $mime,
            'post_title'=>sanitize_text_field((string)($p['title'] ?? (get_the_title($id).' edited'))),
            'post_status'=>'inherit',
            'post_parent'=>absint($p['post_id'] ?? wp_get_post_parent_id($id)),
        ], $file_abs);
        if (is_wp_error($new_id)) return $new_id;
        update_attached_file($new_id,$file_abs);
        wp_update_attachment_metadata($new_id, wp_generate_attachment_metadata($new_id,$file_abs));
        if (isset($p['alt_text'])) update_post_meta($new_id,'_wp_attachment_image_alt',sanitize_text_field((string)$p['alt_text']));
        return ['source_attachment_id'=>$id,'new_attachment'=>self::read($new_id),'relative_file'=>$file_rel];
    }

    public static function metadata(array $body, bool $dry_run) {
        $p = is_array($body['payload'] ?? null) ? $body['payload'] : [];
        $id = absint($p['attachment_id'] ?? ($body['id'] ?? 0));
        if (!$id || get_post_type($id)!=='attachment') return new WP_Error('attachment_not_found','Attachment not found.',['status'=>404]);
        $changes=[];
        foreach (['title'=>'post_title','caption'=>'post_excerpt','description'=>'post_content'] as $in=>$field) {
            if (array_key_exists($in,$p)) $changes[$field]=wp_kses_post((string)$p[$in]);
        }
        if (array_key_exists('alt_text',$p)) $changes['alt_text']=sanitize_text_field((string)$p['alt_text']);
        if ($dry_run) return ['planned'=>true,'attachment_id'=>$id,'changes'=>array_keys($changes)];
        $post=['ID'=>$id];
        foreach (['post_title','post_excerpt','post_content'] as $f) if (isset($changes[$f])) $post[$f]=$changes[$f];
        if (count($post)>1) wp_update_post($post);
        if (isset($changes['alt_text'])) update_post_meta($id,'_wp_attachment_image_alt',$changes['alt_text']);
        return self::read($id);
    }

    private static function read(int $id): array {
        $p=get_post($id);
        return [
            'id'=>$id,'title'=>$p ? $p->post_title : null,'mime'=>get_post_mime_type($id),
            'url'=>wp_get_attachment_url($id),'alt_text'=>get_post_meta($id,'_wp_attachment_image_alt',true),
            'width'=>wp_get_attachment_metadata($id)['width'] ?? null,'height'=>wp_get_attachment_metadata($id)['height'] ?? null
        ];
    }
}
