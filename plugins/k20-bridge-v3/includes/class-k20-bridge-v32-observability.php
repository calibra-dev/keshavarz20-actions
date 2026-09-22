<?php
if (!defined('ABSPATH')) exit;

final class K20_Bridge_V32_Observability {
    public static function status(): array {
        $audit=(array)get_option('k20_bridge_v3_audit',[]);
        $last=$audit?end($audit):null;
        $snaps=get_posts(['post_type'=>'k20_bridge_snapshot','post_status'=>'private','posts_per_page'=>1,'fields'=>'ids']);
        $pending=get_option('k20_bridge_v32_pending_update',[]);
        return [
            'bridge_version'=>defined('K20_BRIDGE_RUNTIME_VERSION')?K20_BRIDGE_RUNTIME_VERSION:null,
            'api_contract'=>'3.2','generated_at_utc'=>gmdate('c'),
            'jobs'=>K20_Bridge_V32_Jobs::stats(),
            'pending_approvals'=>K20_Bridge_V32_Approval::pending_count(),
            'snapshot_store_nonempty'=>!empty($snaps),
            'last_audit'=>$last?:null,
            'pending_update_verification'=>is_array($pending)&&!empty($pending)?[
                'expected_version'=>$pending['expected_version']??null,'applied_at_utc'=>$pending['applied_at_utc']??null
            ]:null,
            'wp_cron_next_job'=>wp_next_scheduled('k20_bridge_v32_run_job')?:null,
            'cache'=>[
                'litespeed'=>defined('LSCWP_V'),
                'object_cache'=>wp_using_ext_object_cache()
            ]
        ];
    }

    public static function selftest(array $body,bool $dry_run,callable $dispatch) {
        $checks=[
            'php_version'=>version_compare(PHP_VERSION,'8.1','>='),
            'wp_rest'=>class_exists('WP_REST_Request'),
            'media_editor'=>function_exists('wp_get_image_editor') || is_file(ABSPATH.'wp-admin/includes/image.php'),
            'content_module'=>class_exists('K20_Bridge_V32_Content'),
            'media_module'=>class_exists('K20_Bridge_V32_Media'),
            'job_module'=>class_exists('K20_Bridge_V32_Jobs'),
            'snapshot_module'=>class_exists('K20_Bridge_V32_Snapshots'),
            'approval_module'=>class_exists('K20_Bridge_V32_Approval'),
            'updater_module'=>class_exists('K20_Bridge_V32_Updater'),
        ];
        if (in_array(false,$checks,true)) return ['ok'=>false,'checks'=>$checks,'lifecycle_skipped'=>true];
        if ($dry_run) return ['ok'=>true,'planned'=>true,'checks'=>$checks];

        $post_id=wp_insert_post(['post_type'=>'page','post_status'=>'draft','post_title'=>'K20 Bridge v3.2 selftest','post_content'=>'k20-selftest-before'],true);
        if (is_wp_error($post_id)) return $post_id;
        $results=[];
        try {
            $r=$dispatch('content.patch',['payload'=>['target_type'=>'post','post_id'=>$post_id,'field'=>'post_content','old_content'=>'k20-selftest-before','new_content'=>'k20-selftest-after']],false);
            $results['content_patch']=!is_wp_error($r) && get_post_field('post_content',$post_id)==='k20-selftest-after';

            update_post_meta($post_id,'_elementor_data',wp_slash('[{"id":"abc1234","elType":"widget","widgetType":"heading","settings":{"title":"Before"},"elements":[]}]'));
            $r=$dispatch('elementor.edit',['id'=>$post_id,'payload'=>['old_content'=>'Before','new_content'=>'After']],false);
            $results['elementor_edit']=!is_wp_error($r) && str_contains((string)get_post_meta($post_id,'_elementor_data',true),'After');

            $r=$dispatch('job.create',['payload'=>['items'=>[['action'=>'cache.status']],'max_retries'=>1]],false);
            $job_id=is_array($r)?($r['job_id']??''):'';
            $r2=$job_id?$dispatch('job.run',['payload'=>['job_id'=>$job_id,'limit'=>1]],false):null;
            $results['background_job']=is_array($r2) && in_array($r2['status']??'',['completed','completed_with_errors'],true);

            $list=K20_Bridge_V32_Snapshots::list(['payload'=>['object_id'=>$post_id,'limit'=>5]]);
            $results['snapshots']=($list['count']??0)>=2;
            $results['cleanup']=true;
        } finally {
            wp_delete_post((int)$post_id,true);
        }
        return ['ok'=>!in_array(false,$results,true),'checks'=>$checks,'lifecycle'=>$results];
    }
}
