<?php
if (!defined('ABSPATH')) exit;

final class K20_Bridge_V32_Content {
    public static function patch(array $body,bool $dry_run) {
        if (!$dry_run) {
            $p=is_array($body['payload']??null)?$body['payload']:[];
            $target=strtolower((string)($p['target_type']??'post'));
            $id=absint($p['post_id']??($body['id']??0));
            if ($target==='post') {
                $field=(string)($p['field']??'post_content');
                $post=get_post($id);
                if ($post && in_array($field,['post_content','post_excerpt','post_title'],true)) {
                    K20_Bridge_V32_Snapshots::capture('post_field',$id,$field,(string)$post->{$field},['action'=>'content.patch']);
                }
            } elseif ($target==='meta') {
                $key=(string)($p['meta_key']??'');
                if ($id && $key==='_elementor_data') {
                    K20_Bridge_V32_Snapshots::capture('post_meta',$id,$key,get_post_meta($id,$key,true),['action'=>'content.patch']);
                }
            }
        }
        return K20_Bridge_V31_Content::patch($body,$dry_run);
    }

    public static function elementor_edit(array $body,bool $dry_run) {
        $id=absint(($body['payload']['post_id']??null) ?: ($body['id']??0));
        if (!$dry_run && $id && get_post($id)) {
            K20_Bridge_V32_Snapshots::capture('post_meta',$id,'_elementor_data',get_post_meta($id,'_elementor_data',true),['action'=>'elementor.edit']);
        }
        return K20_Bridge_V31_Content::elementor_edit($body,$dry_run);
    }

    public static function block_inspect(array $body) {
        $p=is_array($body['payload']??null)?$body['payload']:[];
        $id=absint($p['post_id']??($body['id']??0));
        $post=$id?get_post($id):null;
        if (!$post) return new WP_Error('not_found','Post not found.',['status'=>404]);
        $blocks=parse_blocks((string)$post->post_content);
        $path=self::normalize_path($p['block_path']??[]);
        $block=self::get_block($blocks,$path);
        if (is_wp_error($block)) return $block;
        return [
            'post_id'=>$id,'block_path'=>$path,'block_name'=>$block['blockName']??null,
            'attrs'=>$block['attrs']??[],'inner_html'=>$block['innerHTML']??'',
            'sha256'=>hash('sha256',serialize_block($block))
        ];
    }

    public static function block_patch(array $body,bool $dry_run) {
        $p=is_array($body['payload']??null)?$body['payload']:[];
        $id=absint($p['post_id']??($body['id']??0));
        $post=$id?get_post($id):null;
        if (!$post) return new WP_Error('not_found','Post not found.',['status'=>404]);
        $path=self::normalize_path($p['block_path']??[]);
        $old=(string)($p['old_content']??'');
        $new=(string)($p['new_content']??'');
        if ($old==='') return new WP_Error('invalid_old_content','old_content is required.',['status'=>400]);
        if (strlen($old)>20000 || strlen($new)>250000) return new WP_Error('patch_too_large','Block patch exceeds bounds.',['status'=>400]);

        $blocks=parse_blocks((string)$post->post_content);
        $block=self::get_block($blocks,$path);
        if (is_wp_error($block)) return $block;
        $serialized=serialize_block($block);
        $expected=strtolower((string)($p['expected_sha256']??''));
        $sha=hash('sha256',$serialized);
        if ($expected!=='' && !hash_equals($expected,$sha)) return new WP_Error('stale_block','Block changed since inspection.',['status'=>409]);
        $count=substr_count($serialized,$old);
        if ($count!==1) return new WP_Error($count===0?'no_match':'multiple_matches','Block patch requires exactly one match.',['status'=>409]);
        $patched=str_replace($old,$new,$serialized,$replaced);
        $parsed=parse_blocks($patched);
        if (count($parsed)!==1) return new WP_Error('invalid_block_patch','Patched content does not deserialize to exactly one block.',['status'=>400]);
        if ($dry_run) return ['planned'=>true,'post_id'=>$id,'block_path'=>$path,'before_sha256'=>$sha,'after_sha256'=>hash('sha256',$patched)];

        K20_Bridge_V32_Snapshots::capture('post_field',$id,'post_content',(string)$post->post_content,['action'=>'content.block_patch','block_path'=>$path]);
        $set=self::set_block($blocks,$path,$parsed[0]);
        if (is_wp_error($set)) return $set;
        $result=wp_update_post(['ID'=>$id,'post_content'=>serialize_blocks($blocks)],true);
        if (is_wp_error($result)) return $result;
        return ['post_id'=>$id,'block_path'=>$path,'changed'=>1,'before_sha256'=>$sha,'after_sha256'=>hash('sha256',serialize_block($parsed[0]))];
    }

    public static function elementor_structure(array $body,bool $dry_run) {
        $p=is_array($body['payload']??null)?$body['payload']:[];
        $id=absint($p['post_id']??($body['id']??0));
        $post=$id?get_post($id):null;
        if (!$post) return new WP_Error('not_found','Post not found.',['status'=>404]);
        $raw=(string)get_post_meta($id,'_elementor_data',true);
        $data=json_decode($raw,true);
        if (!is_array($data)) return new WP_Error('invalid_elementor_json','Elementor data is invalid.',['status'=>400]);
        $op=(string)($p['operation']??'');
        $element_id=preg_replace('/[^a-zA-Z0-9_-]/','',(string)($p['element_id']??''));
        if ($element_id==='') return new WP_Error('element_id_required','element_id is required.',['status'=>400]);

        $before=hash('sha256',$raw);
        $changed=false;
        if ($op==='update_settings') {
            $settings=is_array($p['settings']??null)?$p['settings']:[];
            $changed=self::walk_update($data,$element_id,function(&$el) use ($settings){ $el['settings']=array_replace_recursive(is_array($el['settings']??null)?$el['settings']:[],$settings); });
        } elseif ($op==='remove') {
            $changed=self::walk_remove($data,$element_id);
        } elseif ($op==='duplicate') {
            $changed=self::walk_duplicate($data,$element_id);
        } elseif ($op==='insert') {
            $element=is_array($p['element']??null)?$p['element']:[];
            $parent_id=preg_replace('/[^a-zA-Z0-9_-]/','',(string)($p['parent_id']??''));
            $valid=self::validate_element($element);
            if (is_wp_error($valid)) return $valid;
            $changed=self::insert_element($data,$parent_id,$element);
        } elseif ($op==='move') {
            $parent_id=preg_replace('/[^a-zA-Z0-9_-]/','',(string)($p['parent_id']??''));
            $index=max(0,(int)($p['index']??0));
            $found=null;
            if (!self::extract_element($data,$element_id,$found)) return new WP_Error('element_not_found','Element not found.',['status'=>404]);
            $changed=self::insert_element($data,$parent_id,$found,$index);
        } else {
            return new WP_Error('operation_not_allowed','Allowed structural operations: update_settings, remove, duplicate, insert, move.',['status'=>400]);
        }
        if (!$changed) return new WP_Error('element_not_found','Element or parent not found.',['status'=>404]);

        $new=wp_json_encode($data,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
        json_decode($new,true);
        if (json_last_error()!==JSON_ERROR_NONE) return new WP_Error('invalid_elementor_json','Structural edit produced invalid JSON.',['status'=>500]);
        if ($dry_run) return ['planned'=>true,'post_id'=>$id,'operation'=>$op,'element_id'=>$element_id,'before_sha256'=>$before,'after_sha256'=>hash('sha256',$new)];

        K20_Bridge_V32_Snapshots::capture('post_meta',$id,'_elementor_data',$raw,['action'=>'elementor.structure','operation'=>$op,'element_id'=>$element_id]);
        update_post_meta($id,'_elementor_data',wp_slash($new));
        self::clear_elementor_cache();
        return ['post_id'=>$id,'operation'=>$op,'element_id'=>$element_id,'changed'=>1,'before_sha256'=>$before,'after_sha256'=>hash('sha256',$new)];
    }

    private static function normalize_path($path): array {
        if (!is_array($path)) return [];
        return array_map(fn($v)=>max(0,(int)$v),array_slice($path,0,12));
    }
    private static function get_block(array $blocks,array $path) {
        $node=null; $current=$blocks;
        foreach ($path as $idx) {
            if (!isset($current[$idx])) return new WP_Error('block_not_found','Block path not found.',['status'=>404]);
            $node=$current[$idx]; $current=$node['innerBlocks']??[];
        }
        if ($node===null) return new WP_Error('block_path_required','block_path must identify a block.',['status'=>400]);
        return $node;
    }
    private static function set_block(array &$blocks,array $path,array $replacement) {
        $idx=array_shift($path);
        if ($idx===null || !isset($blocks[$idx])) return new WP_Error('block_not_found','Block path not found.',['status'=>404]);
        if (!$path) { $blocks[$idx]=$replacement; return true; }
        if (!isset($blocks[$idx]['innerBlocks']) || !is_array($blocks[$idx]['innerBlocks'])) return new WP_Error('block_not_found','Nested block path not found.',['status'=>404]);
        return self::set_block($blocks[$idx]['innerBlocks'],$path,$replacement);
    }
    private static function walk_update(array &$els,string $id,callable $fn): bool {
        foreach ($els as &$el) {
            if (($el['id']??'')===$id) { $fn($el); return true; }
            if (!empty($el['elements']) && self::walk_update($el['elements'],$id,$fn)) return true;
        }
        return false;
    }
    private static function walk_remove(array &$els,string $id): bool {
        foreach ($els as $i=>&$el) {
            if (($el['id']??'')===$id) { array_splice($els,$i,1); return true; }
            if (!empty($el['elements']) && self::walk_remove($el['elements'],$id)) return true;
        }
        return false;
    }
    private static function walk_duplicate(array &$els,string $id): bool {
        foreach ($els as $i=>&$el) {
            if (($el['id']??'')===$id) {
                $copy=$el; self::renew_ids($copy); array_splice($els,$i+1,0,[$copy]); return true;
            }
            if (!empty($el['elements']) && self::walk_duplicate($el['elements'],$id)) return true;
        }
        return false;
    }
    private static function extract_element(array &$els,string $id,&$found): bool {
        foreach ($els as $i=>&$el) {
            if (($el['id']??'')===$id) { $found=$el; array_splice($els,$i,1); return true; }
            if (!empty($el['elements']) && self::extract_element($el['elements'],$id,$found)) return true;
        }
        return false;
    }
    private static function insert_element(array &$els,string $parent_id,array $element,int $index=PHP_INT_MAX): bool {
        if ($parent_id==='') { array_splice($els,min($index,count($els)),0,[$element]); return true; }
        foreach ($els as &$el) {
            if (($el['id']??'')===$parent_id) {
                if (!isset($el['elements']) || !is_array($el['elements'])) $el['elements']=[];
                array_splice($el['elements'],min($index,count($el['elements'])),0,[$element]); return true;
            }
            if (!empty($el['elements']) && self::insert_element($el['elements'],$parent_id,$element,$index)) return true;
        }
        return false;
    }
    private static function validate_element(array &$el) {
        $type=(string)($el['elType']??'');
        if (!in_array($type,['container','section','column','widget'],true)) return new WP_Error('invalid_element_type','Unsupported Elementor element type.',['status'=>400]);
        if ($type==='widget' && !preg_match('/^[a-z0-9_-]{1,80}$/',(string)($el['widgetType']??''))) return new WP_Error('invalid_widget_type','Widget type is invalid.',['status'=>400]);
        if (empty($el['id'])) $el['id']=substr(bin2hex(random_bytes(8)),0,7);
        $el['id']=preg_replace('/[^a-zA-Z0-9_-]/','',(string)$el['id']);
        if (!isset($el['settings']) || !is_array($el['settings'])) $el['settings']=[];
        if (!isset($el['elements']) || !is_array($el['elements'])) $el['elements']=[];
        return true;
    }
    private static function renew_ids(array &$el): void {
        $el['id']=substr(bin2hex(random_bytes(8)),0,7);
        if (!empty($el['elements']) && is_array($el['elements'])) foreach ($el['elements'] as &$child) self::renew_ids($child);
    }
    private static function clear_elementor_cache(): void {
        if (class_exists('Elementor\\Plugin')) {
            try {
                $plugin=\Elementor\Plugin::instance();
                if (isset($plugin->files_manager) && method_exists($plugin->files_manager,'clear_cache')) $plugin->files_manager->clear_cache();
            } catch (Throwable $e) {}
        }
        if (function_exists('wp_cache_flush')) wp_cache_flush();
    }
}
