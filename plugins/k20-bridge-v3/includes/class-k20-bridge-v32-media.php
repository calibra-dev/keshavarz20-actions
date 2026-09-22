<?php
if (!defined('ABSPATH')) exit;

final class K20_Bridge_V32_Media {
    public static function import_url(array $body,bool $dry_run){ return K20_Bridge_V31_Media::import_url($body,$dry_run); }
    public static function transform(array $body,bool $dry_run){ return K20_Bridge_V31_Media::transform($body,$dry_run); }

    public static function metadata(array $body,bool $dry_run) {
        $p=is_array($body['payload']??null)?$body['payload']:[];
        $id=absint($p['attachment_id']??($body['id']??0));
        if (!$dry_run && $id && get_post_type($id)==='attachment') {
            $post=get_post($id);
            $state=['post'=>['post_title'=>$post->post_title,'post_excerpt'=>$post->post_excerpt,'post_content'=>$post->post_content],'alt_text'=>get_post_meta($id,'_wp_attachment_image_alt',true)];
            K20_Bridge_V32_Snapshots::capture('media_meta',$id,'attachment_meta',$state,['action'=>'media.metadata']);
        }
        return K20_Bridge_V31_Media::metadata($body,$dry_run);
    }

    public static function hash(array $body,bool $dry_run) {
        $p=is_array($body['payload']??null)?$body['payload']:[];
        $id=absint($p['attachment_id']??($body['id']??0));
        $file=$id?get_attached_file($id):'';
        if (!$id || !$file || !is_file($file)) return new WP_Error('attachment_not_found','Attachment file not found.',['status'=>404]);
        $sha=hash_file('sha256',$file);
        if (!$dry_run) update_post_meta($id,'_k20_file_sha256',$sha);
        return ['attachment_id'=>$id,'sha256'=>$sha,'bytes'=>filesize($file),'stored'=>!$dry_run];
    }

    public static function duplicates(array $body) {
        $p=is_array($body['payload']??null)?$body['payload']:[];
        $sha=strtolower((string)($p['sha256']??''));
        if (!preg_match('/^[a-f0-9]{64}$/',$sha)) return new WP_Error('invalid_sha256','sha256 is required.',['status'=>400]);
        $ids=get_posts(['post_type'=>'attachment','post_status'=>'inherit','posts_per_page'=>100,'fields'=>'ids','meta_key'=>'_k20_file_sha256','meta_value'=>$sha]);
        return ['sha256'=>$sha,'count'=>count($ids),'attachment_ids'=>array_map('intval',$ids)];
    }

    public static function optimize(array $body,bool $dry_run) {
        $p=is_array($body['payload']??null)?$body['payload']:[];
        $id=absint($p['attachment_id']??($body['id']??0));
        $src=$id?get_attached_file($id):'';
        if (!$id || !$src || !is_file($src)) return new WP_Error('attachment_not_found','Attachment file not found.',['status'=>404]);
        $target_mime=(string)($p['mime']??'image/webp');
        if (!in_array($target_mime,['image/webp','image/jpeg','image/png'],true)) return new WP_Error('mime_not_allowed','Output mime is not allowed.',['status'=>400]);
        $max=max(256,min(4096,(int)($p['max_dimension']??1920)));
        $quality=max(40,min(95,(int)($p['quality']??82)));
        if ($dry_run) return ['planned'=>true,'attachment_id'=>$id,'mime'=>$target_mime,'max_dimension'=>$max,'quality'=>$quality];

        require_once ABSPATH.'wp-admin/includes/image.php';
        $editor=wp_get_image_editor($src);
        if (is_wp_error($editor)) return $editor;
        $size=$editor->get_size();
        if (max((int)$size['width'],(int)$size['height'])>$max) {
            if ($size['width'] >= $size['height']) { $w=$max; $h=(int)round($size['height']*$max/$size['width']); }
            else { $h=$max; $w=(int)round($size['width']*$max/$size['height']); }
            $r=$editor->resize(max(1,$w),max(1,$h),false); if (is_wp_error($r)) return $r;
        }
        $editor->set_quality($quality);
        $dir=dirname($src); $ext=$target_mime==='image/webp'?'webp':($target_mime==='image/png'?'png':'jpg');
        $dest=wp_unique_filename($dir,pathinfo($src,PATHINFO_FILENAME).'-optimized.'.$ext);
        $saved=$editor->save($dir.'/'.$dest,$target_mime);
        if (is_wp_error($saved)) return $saved;
        $new_id=self::insert_generated($id,$saved['path'],$saved['mime-type']??$target_mime,' optimized');
        if (is_wp_error($new_id)) return $new_id;
        $sha=hash_file('sha256',$saved['path']); update_post_meta($new_id,'_k20_file_sha256',$sha);
        return ['source_attachment_id'=>$id,'new_attachment_id'=>$new_id,'url'=>wp_get_attachment_url($new_id),'sha256'=>$sha,'bytes'=>filesize($saved['path']),'mime'=>get_post_mime_type($new_id)];
    }

    public static function focal_crop(array $body,bool $dry_run) {
        $p=is_array($body['payload']??null)?$body['payload']:[];
        $id=absint($p['attachment_id']??($body['id']??0));
        $src=$id?get_attached_file($id):'';
        if (!$id || !$src || !is_file($src)) return new WP_Error('attachment_not_found','Attachment file not found.',['status'=>404]);
        $tw=max(1,min(6000,(int)($p['width']??1200))); $th=max(1,min(6000,(int)($p['height']??1200)));
        $fx=max(0,min(1,(float)($p['focal_x']??0.5))); $fy=max(0,min(1,(float)($p['focal_y']??0.5)));
        if ($dry_run) return ['planned'=>true,'attachment_id'=>$id,'width'=>$tw,'height'=>$th,'focal_x'=>$fx,'focal_y'=>$fy];

        require_once ABSPATH.'wp-admin/includes/image.php';
        $editor=wp_get_image_editor($src); if (is_wp_error($editor)) return $editor;
        $s=$editor->get_size(); $sw=(int)$s['width']; $sh=(int)$s['height'];
        $target_ratio=$tw/$th; $source_ratio=$sw/$sh;
        if ($source_ratio>$target_ratio) { $ch=$sh; $cw=(int)round($sh*$target_ratio); } else { $cw=$sw; $ch=(int)round($sw/$target_ratio); }
        $cx=max(0,min($sw-$cw,(int)round(($sw*$fx)-($cw/2))));
        $cy=max(0,min($sh-$ch,(int)round(($sh*$fy)-($ch/2))));
        $r=$editor->crop($cx,$cy,$cw,$ch,$tw,$th,false); if (is_wp_error($r)) return $r;
        $dir=dirname($src); $ext=pathinfo($src,PATHINFO_EXTENSION);
        $dest=wp_unique_filename($dir,pathinfo($src,PATHINFO_FILENAME).'-focal.'.$ext);
        $saved=$editor->save($dir.'/'.$dest); if (is_wp_error($saved)) return $saved;
        $new_id=self::insert_generated($id,$saved['path'],$saved['mime-type']??get_post_mime_type($id),' focal crop');
        if (is_wp_error($new_id)) return $new_id;
        return ['source_attachment_id'=>$id,'new_attachment_id'=>$new_id,'url'=>wp_get_attachment_url($new_id),'width'=>$tw,'height'=>$th];
    }

    public static function watermark(array $body,bool $dry_run) {
        $p=is_array($body['payload']??null)?$body['payload']:[];
        $id=absint($p['attachment_id']??($body['id']??0));
        $wm=absint($p['watermark_attachment_id']??0);
        $src=$id?get_attached_file($id):''; $wmf=$wm?get_attached_file($wm):'';
        if (!$src || !$wmf || !is_file($src) || !is_file($wmf)) return new WP_Error('attachment_not_found','Source or watermark attachment not found.',['status'=>404]);
        if (!class_exists('Imagick')) return new WP_Error('imagick_required','Imagick is required for watermark compositing.',['status'=>501]);
        $opacity=max(0.05,min(1,(float)($p['opacity']??0.35)));
        $scale=max(0.05,min(0.8,(float)($p['scale']??0.22)));
        $position=(string)($p['position']??'bottom-right');
        if ($dry_run) return ['planned'=>true,'attachment_id'=>$id,'watermark_attachment_id'=>$wm,'opacity'=>$opacity,'scale'=>$scale,'position'=>$position];

        try {
            $image=new \Imagick($src); $mark=new \Imagick($wmf);
            $iw=$image->getImageWidth(); $ih=$image->getImageHeight();
            $target=max(20,(int)round($iw*$scale));
            $mark->thumbnailImage($target,0,true);
            if (method_exists($mark,'evaluateImage')) $mark->evaluateImage(\Imagick::EVALUATE_MULTIPLY,$opacity,\Imagick::CHANNEL_ALPHA);
            $mw=$mark->getImageWidth(); $mh=$mark->getImageHeight(); $pad=max(10,(int)round($iw*0.02));
            $x=$iw-$mw-$pad; $y=$ih-$mh-$pad;
            if ($position==='bottom-left') { $x=$pad; }
            elseif ($position==='top-right') { $y=$pad; }
            elseif ($position==='top-left') { $x=$pad; $y=$pad; }
            elseif ($position==='center') { $x=(int)(($iw-$mw)/2); $y=(int)(($ih-$mh)/2); }
            $image->compositeImage($mark,\Imagick::COMPOSITE_OVER,$x,$y);
            $dir=dirname($src); $ext=pathinfo($src,PATHINFO_EXTENSION);
            $dest=$dir.'/'.wp_unique_filename($dir,pathinfo($src,PATHINFO_FILENAME).'-watermarked.'.$ext);
            $image->writeImage($dest); $mime=get_post_mime_type($id);
            $new_id=self::insert_generated($id,$dest,$mime,' watermarked');
            $image->clear(); $mark->clear();
            if (is_wp_error($new_id)) return $new_id;
            return ['source_attachment_id'=>$id,'new_attachment_id'=>$new_id,'url'=>wp_get_attachment_url($new_id)];
        } catch (Throwable $e) {
            return new WP_Error('watermark_failed','Watermark operation failed.',['status'=>500]);
        }
    }

    private static function insert_generated(int $source_id,string $path,string $mime,string $suffix) {
        require_once ABSPATH.'wp-admin/includes/image.php';
        $new_id=wp_insert_attachment(['post_mime_type'=>$mime,'post_title'=>get_the_title($source_id).$suffix,'post_status'=>'inherit','post_parent'=>wp_get_post_parent_id($source_id)],$path);
        if (is_wp_error($new_id)) return $new_id;
        update_attached_file($new_id,$path);
        wp_update_attachment_metadata($new_id,wp_generate_attachment_metadata($new_id,$path));
        $alt=get_post_meta($source_id,'_wp_attachment_image_alt',true); if ($alt!=='') update_post_meta($new_id,'_wp_attachment_image_alt',$alt);
        return $new_id;
    }
}
