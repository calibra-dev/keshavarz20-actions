<?php
if (!defined('ABSPATH')) exit;

final class K20_Bridge_V32_Jobs {
    private const OPTION='k20_bridge_v31_jobs';
    private const LIMIT=100;
    private const ITEM_LIMIT=500;

    public static function boot(): void { add_action('k20_bridge_v32_run_job',[__CLASS__,'run_scheduled'],10,1); }

    public static function create(array $body,bool $dry_run) {
        $p=is_array($body['payload']??null)?$body['payload']:[];
        $items=is_array($p['items']??null)?array_values($p['items']):[];
        if (!$items) return new WP_Error('job_empty','payload.items is required.',['status'=>400]);
        if (count($items)>self::ITEM_LIMIT) return new WP_Error('job_too_large','Job exceeds 500 items.',['status'=>400]);
        $max_retries=max(0,min(5,(int)($p['max_retries']??2)));
        $backoff=max(10,min(3600,(int)($p['backoff_seconds']??30)));
        foreach ($items as $item) {
            if (!is_array($item) || empty($item['action'])) return new WP_Error('job_item_invalid','Every job item requires an action.',['status'=>400]);
            if (str_starts_with((string)$item['action'],'job.') || in_array((string)$item['action'],['approval.execute','approval.status'],true)) return new WP_Error('job_recursion','Job-control and approval actions cannot be queued.',['status'=>400]);
        }
        if ($dry_run) return ['planned'=>true,'items'=>count($items),'max_retries'=>$max_retries,'backoff_seconds'=>$backoff];
        $id='job_'.substr(hash('sha256',wp_json_encode($items).microtime(true).wp_rand()),0,20);
        $jobs=self::all();
        $jobs[$id]=[
            'id'=>$id,'status'=>'queued','created_at_utc'=>gmdate('c'),'updated_at_utc'=>gmdate('c'),
            'cursor'=>0,'total'=>count($items),'success'=>0,'failed'=>0,'retrying'=>0,'dead_letter'=>0,
            'items'=>$items,'attempts'=>array_fill(0,count($items),0),'receipts'=>[],'dead_letters'=>[],
            'max_retries'=>$max_retries,'backoff_seconds'=>$backoff
        ];
        self::save($jobs); wp_schedule_single_event(time()+5,'k20_bridge_v32_run_job',[$id]);
        return self::summary($jobs[$id]);
    }

    public static function status(array $body) {
        $id=sanitize_text_field((string)(($body['payload']['job_id']??null)?:($body['job_id']??'')));
        $jobs=self::all(); if (!$id || !isset($jobs[$id])) return new WP_Error('job_not_found','Job not found.',['status'=>404]);
        return self::summary($jobs[$id],true);
    }

    public static function retry_failed(array $body,bool $dry_run) {
        $id=sanitize_text_field((string)($body['payload']['job_id']??''));
        $jobs=self::all(); if (!$id || !isset($jobs[$id])) return new WP_Error('job_not_found','Job not found.',['status'=>404]);
        $job=$jobs[$id]; $indices=array_map('intval',array_keys($job['dead_letters']??[]));
        if ($dry_run) return ['planned'=>true,'job_id'=>$id,'dead_letter_items'=>count($indices)];
        if (!$indices) return ['job_id'=>$id,'requeued'=>0,'status'=>$job['status']];
        $newItems=[]; foreach ($indices as $i) if (isset($job['items'][$i])) $newItems[]=$job['items'][$i];
        $fake=['payload'=>['items'=>$newItems,'max_retries'=>$job['max_retries']??2,'backoff_seconds'=>$job['backoff_seconds']??30]];
        return self::create($fake,false);
    }

    public static function run(array $body,bool $dry_run,callable $dispatch) {
        $id=sanitize_text_field((string)(($body['payload']['job_id']??null)?:($body['job_id']??'')));
        $limit=max(1,min(25,(int)($body['payload']['limit']??10)));
        if ($dry_run) return ['planned'=>true,'job_id'=>$id,'limit'=>$limit];
        return self::process($id,$limit,$dispatch);
    }

    public static function run_scheduled(string $id): void {
        if (!class_exists('K20_Bridge_V3')) return;
        self::process($id,10,function($action,$item,$dry){ return K20_Bridge_V3::dispatch_for_job($action,$item,$dry); });
        $jobs=self::all();
        if (isset($jobs[$id]) && in_array($jobs[$id]['status'],['running','retry_wait'],true)) {
            $delay=max(15,(int)($jobs[$id]['backoff_seconds']??30));
            wp_schedule_single_event(time()+$delay,'k20_bridge_v32_run_job',[$id]);
        }
    }

    private static function process(string $id,int $limit,callable $dispatch) {
        $jobs=self::all(); if (!$id || !isset($jobs[$id])) return new WP_Error('job_not_found','Job not found.',['status'=>404]);
        $job=$jobs[$id]; if (in_array($job['status'],['completed','completed_with_errors','cancelled'],true)) return self::summary($job,true);
        $job['status']='running'; $processed=0;
        while ($processed<$limit && $job['cursor']<$job['total']) {
            $i=$job['cursor']; $item=$job['items'][$i]; $action=(string)$item['action'];
            $job['attempts'][$i]=(int)($job['attempts'][$i]??0)+1;
            $r=$dispatch($action,$item,!empty($item['dry_run']));
            if (is_wp_error($r)) {
                $attempt=$job['attempts'][$i]; $max=(int)($job['max_retries']??2);
                if ($attempt <= $max) {
                    $job['retrying']=(int)($job['retrying']??0)+1;
                    $job['status']='retry_wait';
                    $job['receipts'][]=['index'=>$i,'action'=>$action,'ok'=>false,'attempt'=>$attempt,'retry'=>true,'error'=>$r->get_error_code()];
                    break;
                }
                $job['failed']++; $job['dead_letter']=(int)($job['dead_letter']??0)+1;
                $job['dead_letters'][$i]=['action'=>$action,'attempts'=>$attempt,'error'=>$r->get_error_code(),'message'=>$r->get_error_message()];
                $job['receipts'][]=['index'=>$i,'action'=>$action,'ok'=>false,'attempt'=>$attempt,'dead_letter'=>true,'error'=>$r->get_error_code()];
                $job['cursor']=$i+1;
            } else {
                $job['success']++; $job['receipts'][]=['index'=>$i,'action'=>$action,'ok'=>true,'attempt'=>$job['attempts'][$i]];
                $job['cursor']=$i+1;
            }
            $processed++; $job['updated_at_utc']=gmdate('c');
        }
        if ($job['cursor'] >= $job['total']) $job['status']=$job['failed']>0?'completed_with_errors':'completed';
        $jobs[$id]=$job; self::save($jobs); return self::summary($job,true);
    }

    public static function stats(): array {
        $jobs=self::all(); $s=['total_jobs'=>count($jobs),'queued'=>0,'running'=>0,'retry_wait'=>0,'failed_items'=>0,'dead_letter_items'=>0];
        foreach ($jobs as $j) {
            $st=(string)($j['status']??''); if (isset($s[$st])) $s[$st]++;
            $s['failed_items']+=(int)($j['failed']??0); $s['dead_letter_items']+=(int)($j['dead_letter']??0);
        }
        return $s;
    }

    private static function summary(array $j,bool $detail=false): array {
        $out=['job_id'=>$j['id'],'status'=>$j['status'],'cursor'=>$j['cursor'],'total'=>$j['total'],'success'=>$j['success'],'failed'=>$j['failed'],'retrying'=>(int)($j['retrying']??0),'dead_letter'=>(int)($j['dead_letter']??0),'max_retries'=>(int)($j['max_retries']??0),'created_at_utc'=>$j['created_at_utc'],'updated_at_utc'=>$j['updated_at_utc']];
        if ($detail) { $out['receipts']=array_slice($j['receipts']??[],-50); $out['dead_letters']=array_slice($j['dead_letters']??[],0,50,true); }
        return $out;
    }
    private static function all(): array { $v=get_option(self::OPTION,[]); return is_array($v)?$v:[]; }
    private static function save(array $jobs): void { if (count($jobs)>self::LIMIT) $jobs=array_slice($jobs,-self::LIMIT,null,true); update_option(self::OPTION,$jobs,false); }
}
K20_Bridge_V32_Jobs::boot();
