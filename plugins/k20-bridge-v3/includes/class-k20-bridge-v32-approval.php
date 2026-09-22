<?php
if (!defined('ABSPATH')) exit;

final class K20_Bridge_V32_Approval {
    private const OPTION='k20_bridge_v32_approvals';
    private const LIMIT=80;
    private const TTL=1800;

    public static function requires(string $action,array $body): bool {
        if (!empty($body['_approval_bypass'])) return false;
        if (in_array($action,['update.apply','update.rollback','snapshot.rollback'],true)) return true;
        if ($action==='elementor.structure') {
            $op=(string)($body['payload']['operation']??'');
            return in_array($op,['remove','move','insert','duplicate'],true);
        }
        if ($action==='batch') {
            $items=is_array($body['payload']['items']??null)?$body['payload']['items']:[];
            return count($items)>10;
        }
        if ($action==='job.create') {
            $items=is_array($body['payload']['items']??null)?$body['payload']['items']:[];
            return count($items)>100;
        }
        return false;
    }

    public static function gate(string $action,array $body) {
        $approvals=self::all();
        $fingerprint=hash('sha256',wp_json_encode([$action,$body],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));
        foreach ($approvals as $id=>$row) {
            if (($row['fingerprint']??'')===$fingerprint && ($row['status']??'')==='pending' && (int)($row['expires']??0)>time()) {
                return new WP_Error('approval_required','This operation requires a second-phase approval.',['status'=>409,'approval_id'=>$id,'fingerprint'=>$fingerprint,'expires_at_utc'=>gmdate('c',(int)$row['expires'])]);
            }
        }
        $id='ap_'.substr(hash('sha256',$fingerprint.microtime(true).wp_rand()),0,18);
        $approvals[$id]=[
            'id'=>$id,'status'=>'pending','fingerprint'=>$fingerprint,'action'=>$action,
            'request'=>$body,'created'=>time(),'expires'=>time()+self::TTL
        ];
        self::save($approvals);
        return new WP_Error('approval_required','This operation requires a second-phase approval.',['status'=>409,'approval_id'=>$id,'fingerprint'=>$fingerprint,'expires_at_utc'=>gmdate('c',time()+self::TTL)]);
    }

    public static function status(array $body) {
        $id=sanitize_text_field((string)($body['payload']['approval_id']??''));
        $rows=self::all();
        if (!$id || !isset($rows[$id])) return new WP_Error('approval_not_found','Approval not found.',['status'=>404]);
        $r=$rows[$id];
        if (($r['status']??'')==='pending' && (int)$r['expires']<time()) { $r['status']='expired'; $rows[$id]=$r; self::save($rows); }
        return ['approval_id'=>$id,'status'=>$r['status'],'action'=>$r['action'],'created_at_utc'=>gmdate('c',(int)$r['created']),'expires_at_utc'=>gmdate('c',(int)$r['expires']),'fingerprint'=>$r['fingerprint']];
    }

    public static function execute(array $body,bool $dry_run,callable $dispatch) {
        $p=is_array($body['payload']??null)?$body['payload']:[];
        $id=sanitize_text_field((string)($p['approval_id']??''));
        $fingerprint=strtolower((string)($p['fingerprint']??''));
        $rows=self::all();
        if (!$id || !isset($rows[$id])) return new WP_Error('approval_not_found','Approval not found.',['status'=>404]);
        $r=$rows[$id];
        if (($r['status']??'')!=='pending') return new WP_Error('approval_not_pending','Approval is not pending.',['status'=>409]);
        if ((int)$r['expires']<time()) return new WP_Error('approval_expired','Approval expired.',['status'=>409]);
        if (!hash_equals((string)$r['fingerprint'],$fingerprint)) return new WP_Error('approval_fingerprint_mismatch','Approval fingerprint mismatch.',['status'=>409]);
        if ($dry_run) return ['planned'=>true,'approval_id'=>$id,'action'=>$r['action']];

        $frozen=$r['request'];
        $frozen['_approval_bypass']=true;
        $rows[$id]['status']='executing'; self::save($rows);
        $result=$dispatch((string)$r['action'],$frozen,false);
        $rows=self::all();
        if (isset($rows[$id])) {
            $rows[$id]['status']=is_wp_error($result)?'failed':'executed';
            $rows[$id]['finished']=time();
            $rows[$id]['result_code']=is_wp_error($result)?$result->get_error_code():'ok';
            self::save($rows);
        }
        return $result;
    }

    public static function pending_count(): int {
        $n=0; foreach (self::all() as $r) if (($r['status']??'')==='pending' && (int)($r['expires']??0)>time()) $n++; return $n;
    }

    private static function all(): array {
        $v=get_option(self::OPTION,[]); return is_array($v)?$v:[];
    }
    private static function save(array $rows): void {
        uasort($rows,fn($a,$b)=>(int)($b['created']??0)<=>(int)($a['created']??0));
        if (count($rows)>self::LIMIT) $rows=array_slice($rows,0,self::LIMIT,true);
        update_option(self::OPTION,$rows,false);
    }
}
