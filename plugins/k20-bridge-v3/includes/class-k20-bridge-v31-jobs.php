<?php
if (!defined('ABSPATH')) exit;

final class K20_Bridge_V31_Jobs {
    private const OPTION='k20_bridge_v31_jobs';
    private const LIMIT=100;
    private const ITEM_LIMIT=500;

    public static function boot(): void {
        add_action('k20_bridge_v31_run_job',[__CLASS__,'run_scheduled'],10,1);
    }

    public static function create(array $body, bool $dry_run) {
        $p=is_array($body['payload'] ?? null)?$body['payload']:[];
        $items=is_array($p['items'] ?? null)?array_values($p['items']):[];
        if (!$items) return new WP_Error('job_empty','payload.items is required.',['status'=>400]);
        if (count($items)>self::ITEM_LIMIT) return new WP_Error('job_too_large','Job exceeds 500 items.',['status'=>400]);
        foreach ($items as $item) {
            if (!is_array($item) || empty($item['action'])) return new WP_Error('job_item_invalid','Every job item requires an action.',['status'=>400]);
            if (in_array((string)$item['action'],['job.create','job.run','job.status'],true)) return new WP_Error('job_recursion','Job actions cannot enqueue job-control actions.',['status'=>400]);
        }
        if ($dry_run) return ['planned'=>true,'items'=>count($items)];
        $id='job_'.substr(hash('sha256',wp_json_encode($items).microtime(true).wp_rand()),0,20);
        $jobs=self::all();
        $jobs[$id]=[
            'id'=>$id,'status'=>'queued','created_at_utc'=>gmdate('c'),'updated_at_utc'=>gmdate('c'),
            'cursor'=>0,'total'=>count($items),'success'=>0,'failed'=>0,'items'=>$items,'receipts'=>[]
        ];
        self::save($jobs);
        wp_schedule_single_event(time()+5,'k20_bridge_v31_run_job',[$id]);
        return self::summary($jobs[$id]);
    }

    public static function status(array $body) {
        $id=sanitize_text_field((string)(($body['payload']['job_id'] ?? null) ?: ($body['job_id'] ?? '')));
        $jobs=self::all();
        if (!$id || !isset($jobs[$id])) return new WP_Error('job_not_found','Job not found.',['status'=>404]);
        return self::summary($jobs[$id],true);
    }

    public static function run(array $body, bool $dry_run, callable $dispatch) {
        $id=sanitize_text_field((string)(($body['payload']['job_id'] ?? null) ?: ($body['job_id'] ?? '')));
        $limit=max(1,min(25,(int)($body['payload']['limit'] ?? 10)));
        if ($dry_run) return ['planned'=>true,'job_id'=>$id,'limit'=>$limit];
        return self::process($id,$limit,$dispatch);
    }

    public static function run_scheduled(string $id): void {
        if (!class_exists('K20_Bridge_V3')) return;
        self::process($id,10,function($action,$item,$dry){ return K20_Bridge_V3::dispatch_for_job($action,$item,$dry); });
        $jobs=self::all();
        if (isset($jobs[$id]) && $jobs[$id]['status']==='running') wp_schedule_single_event(time()+15,'k20_bridge_v31_run_job',[$id]);
    }

    private static function process(string $id,int $limit,callable $dispatch) {
        $jobs=self::all();
        if (!$id || !isset($jobs[$id])) return new WP_Error('job_not_found','Job not found.',['status'=>404]);
        $job=$jobs[$id];
        if (in_array($job['status'],['completed','cancelled'],true)) return self::summary($job,true);
        $job['status']='running';
        $end=min($job['total'],$job['cursor']+$limit);
        for ($i=$job['cursor'];$i<$end;$i++) {
            $item=$job['items'][$i];
            $action=(string)$item['action'];
            $r=$dispatch($action,$item,!empty($item['dry_run']));
            if (is_wp_error($r)) {
                $job['failed']++;
                $job['receipts'][]=['index'=>$i,'action'=>$action,'ok'=>false,'error'=>$r->get_error_code()];
            } else {
                $job['success']++;
                $job['receipts'][]=['index'=>$i,'action'=>$action,'ok'=>true];
            }
            $job['cursor']=$i+1;
            $job['updated_at_utc']=gmdate('c');
        }
        if ($job['cursor'] >= $job['total']) $job['status']=$job['failed']>0?'completed_with_errors':'completed';
        $jobs[$id]=$job; self::save($jobs);
        return self::summary($job,true);
    }

    private static function summary(array $j,bool $with_receipts=false): array {
        $out=['job_id'=>$j['id'],'status'=>$j['status'],'cursor'=>$j['cursor'],'total'=>$j['total'],'success'=>$j['success'],'failed'=>$j['failed'],'created_at_utc'=>$j['created_at_utc'],'updated_at_utc'=>$j['updated_at_utc']];
        if ($with_receipts) $out['receipts']=array_slice($j['receipts'],-50);
        return $out;
    }
    private static function all(): array { $v=get_option(self::OPTION,[]); return is_array($v)?$v:[]; }
    private static function save(array $jobs): void {
        if (count($jobs)>self::LIMIT) $jobs=array_slice($jobs,-self::LIMIT,null,true);
        update_option(self::OPTION,$jobs,false);
    }
}
K20_Bridge_V31_Jobs::boot();
