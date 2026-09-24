<?php
if (!defined('ABSPATH')) exit;

final class K20_Bridge_V33_Snippets {
    private const MAX_CODE_BYTES=102400;
    private const BASE='/code-snippets/v1/snippets';

    public static function list(array $body) {
        $p=self::payload($body);
        $query=['per_page'=>max(1,min(100,(int)($p['per_page']??50)))];
        if (!empty($p['search'])) $query['search']=sanitize_text_field((string)$p['search']);
        if (!empty($p['status'])) $query['status']=sanitize_key((string)$p['status']);
        $data=self::request('GET',self::BASE,[],$query);
        if (is_wp_error($data)) return $data;
        $items=is_array($data)?($data['snippets']??($data['data']??$data)):[];
        $out=[];
        foreach (is_array($items)?$items:[] as $row) {
            if (!is_array($row)) continue;
            $out[]=self::summary($row);
        }
        return ['count'=>count($out),'items'=>$out];
    }

    public static function read(array $body) {
        $id=absint(self::payload($body)['snippet_id']??($body['id']??0));
        if (!$id) return new WP_Error('snippet_id_required','snippet_id is required.',['status'=>400]);
        $row=self::request('GET',self::BASE.'/'.$id);
        if (is_wp_error($row)) return $row;
        return self::detail(is_array($row)?$row:[]);
    }

    public static function validate(array $body) {
        $code=(string)(self::payload($body)['snippet_code']??'');
        $check=self::validate_code($code);
        if (is_wp_error($check)) return $check;
        return ['valid'=>true,'bytes'=>strlen($code),'sha256'=>hash('sha256',$code),'policy'=>'draft-only-no-arbitrary-exec'];
    }

    public static function create_draft(array $body,bool $dry_run) {
        $p=self::payload($body);
        $name=sanitize_text_field((string)($p['name']??$p['title']??''));
        $code=(string)($p['snippet_code']??'');
        if ($name==='') return new WP_Error('snippet_name_required','Snippet name is required.',['status'=>400]);
        $check=self::validate_code($code); if (is_wp_error($check)) return $check;
        $payload=self::write_payload($p,$code,$name);
        $payload['active']=false;
        $payload['network']=false;
        if ($dry_run) return ['planned'=>true,'name'=>$name,'active'=>false,'bytes'=>strlen($code),'sha256'=>hash('sha256',$code)];
        $row=self::request('POST',self::BASE,$payload);
        if (is_wp_error($row)) return $row;
        $detail=self::detail(is_array($row)?$row:[]);
        $detail['forced_inactive']=true;
        return $detail;
    }

    public static function update_draft(array $body,bool $dry_run) {
        $p=self::payload($body);
        $id=absint($p['snippet_id']??($body['id']??0));
        if (!$id) return new WP_Error('snippet_id_required','snippet_id is required.',['status'=>400]);
        $before=self::request('GET',self::BASE.'/'.$id);
        if (is_wp_error($before)) return $before;
        if (!is_array($before)) return new WP_Error('snippet_invalid','Snippet response is invalid.',['status'=>502]);
        if (!empty($before['active'])) return new WP_Error('snippet_active','Active snippets cannot be edited by Bridge. Deactivate with approval first.',['status'=>409]);

        $code=array_key_exists('snippet_code',$p)?(string)$p['snippet_code']:(string)($before['code']??'');
        $check=self::validate_code($code); if (is_wp_error($check)) return $check;
        $name=sanitize_text_field((string)($p['name']??($before['name']??'')));
        if ($name==='') return new WP_Error('snippet_name_required','Snippet name is required.',['status'=>400]);
        $payload=self::write_payload(array_merge($before,$p),$code,$name);
        $payload['active']=false;
        $payload['network']=false;
        if ($dry_run) return ['planned'=>true,'snippet_id'=>$id,'name'=>$name,'active'=>false,'bytes'=>strlen($code),'sha256'=>hash('sha256',$code)];

        K20_Bridge_V32_Snapshots::capture('snippet',$id,'snippet',$before,['action'=>'snippet.update_draft']);
        $row=self::request('PUT',self::BASE.'/'.$id,$payload);
        if (is_wp_error($row)) return $row;
        $detail=self::detail(is_array($row)?$row:[]);
        $detail['forced_inactive']=true;
        return $detail;
    }

    public static function deactivate(array $body,bool $dry_run) {
        $p=self::payload($body);
        $id=absint($p['snippet_id']??($body['id']??0));
        if (!$id) return new WP_Error('snippet_id_required','snippet_id is required.',['status'=>400]);
        $before=self::request('GET',self::BASE.'/'.$id);
        if (is_wp_error($before)) return $before;
        if ($dry_run) return ['planned'=>true,'snippet_id'=>$id,'was_active'=>!empty($before['active'])];
        K20_Bridge_V32_Snapshots::capture('snippet',$id,'snippet',$before,['action'=>'snippet.deactivate']);
        $row=self::request('POST',self::BASE.'/'.$id.'/deactivate');
        if (is_wp_error($row)) return $row;
        return ['snippet_id'=>$id,'deactivated'=>true,'was_active'=>!empty($before['active'])];
    }

    private static function validate_code(string $code) {
        if ($code==='') return new WP_Error('snippet_code_required','snippet_code is required.',['status'=>400]);
        if (strlen($code)>self::MAX_CODE_BYTES) return new WP_Error('snippet_code_too_large','Snippet code exceeds 100 KiB.',['status'=>400]);
        if (strpos($code,"\0")!==false) return new WP_Error('snippet_code_invalid','Snippet contains a NUL byte.',['status'=>400]);
        if (preg_match('/<\?(?:php)?|\?>/i',$code)) return new WP_Error('php_tags_not_allowed','Do not include PHP opening/closing tags in snippets.',['status'=>400]);

        $rules=[
            'arbitrary_execution'=>'/\b(?:eval|exec|shell_exec|system|passthru|proc_open|popen|pcntl_exec)\s*\(/i',
            'shell_backticks'=>'/\x60[^\x60]*\x60/s',
            'raw_sql'=>'/(?:\$wpdb\b|\bmysqli_|\bmysql_|\bPDO\b)/i',
            'filesystem_write'=>'/\b(?:file_put_contents|fopen|fwrite|unlink|rename|copy|chmod|chown|mkdir|rmdir)\s*\(/i',
            'user_admin'=>'/\b(?:wp_create_user|wp_insert_user|wp_update_user|add_role|remove_role|set_role|add_cap|remove_cap)\s*\(/i',
            'price_write'=>'/(?:\bset_(?:regular_)?price\s*\(|\bset_sale_price\s*\(|[\'"]_(?:price|regular_price|sale_price)[\'"])/i'
        ];
        foreach ($rules as $name=>$regex) if (preg_match($regex,$code)) {
            return new WP_Error('snippet_policy_blocked','Snippet violates the guarded code policy.',['status'=>400,'rule'=>$name]);
        }
        return true;
    }

    private static function write_payload(array $p,string $code,string $name): array {
        $scope=(string)($p['scope']??'global');
        $allowed_scopes=['global','front-end','admin','content'];
        if (!in_array($scope,$allowed_scopes,true)) $scope='global';
        $tags=[];
        foreach (is_array($p['tags']??null)?$p['tags']:[] as $tag) {
            $tag=sanitize_text_field((string)$tag);
            if ($tag!=='') $tags[]=$tag;
        }
        return [
            'name'=>$name,
            'desc'=>wp_kses_post((string)($p['desc']??'')),
            'code'=>$code,
            'tags'=>array_values(array_unique($tags)),
            'scope'=>$scope,
            'priority'=>max(1,min(100,(int)($p['priority']??10))),
            'active'=>false,
            'network'=>false
        ];
    }

    private static function summary(array $row): array {
        return [
            'snippet_id'=>(int)($row['id']??0),
            'name'=>$row['name']??null,
            'active'=>!empty($row['active']),
            'scope'=>$row['scope']??null,
            'priority'=>$row['priority']??null,
            'tags'=>is_array($row['tags']??null)?array_values($row['tags']):[],
            'modified'=>$row['modified']??null,
            'code_error'=>$row['code_error']??null
        ];
    }

    private static function detail(array $row): array {
        $out=self::summary($row);
        $code=(string)($row['code']??'');
        $out['snippet_code']=$code;
        $out['code_sha256']=hash('sha256',$code);
        $out['code_bytes']=strlen($code);
        $out['desc']=$row['desc']??'';
        $out['locked']=!empty($row['locked']);
        $out['trashed']=!empty($row['trashed']);
        return $out;
    }

    private static function request(string $method,string $route,array $payload=[],array $query=[]) {
        $req=new WP_REST_Request($method,$route);
        if ($query) $req->set_query_params($query);
        if ($payload) $req->set_body_params($payload);
        $res=rest_do_request($req);
        if (is_wp_error($res)) return $res;
        $status=$res->get_status();
        $data=$res->get_data();
        if ($status<200 || $status>=300) {
            $msg=is_array($data)&&isset($data['message'])?(string)$data['message']:'Code Snippets REST request failed.';
            return new WP_Error('snippet_rest_error',$msg,['status'=>$status]);
        }
        return $data;
    }

    private static function payload(array $body): array { return is_array($body['payload']??null)?$body['payload']:[]; }
}
