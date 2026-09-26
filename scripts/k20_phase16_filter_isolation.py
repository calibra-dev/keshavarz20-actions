#!/usr/bin/env python3
import os,json,requests,time,hashlib
BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
SNIP=BASE+"/wp-json/code-snippets/v1/snippets"
name="K20 TEMP Phase16 Filter Isolation"
code=r'''
if ( ! defined( 'ABSPATH' ) ) { exit; }

function k20_p16_cb_name( $cb ) {
    if ( is_string( $cb ) ) return $cb;
    if ( $cb instanceof Closure ) return 'Closure';
    if ( is_array( $cb ) && count( $cb ) >= 2 ) {
        return ( is_object( $cb[0] ) ? get_class( $cb[0] ) : (string) $cb[0] ) . '::' . (string) $cb[1];
    }
    if ( is_object( $cb ) && method_exists( $cb, '__invoke' ) ) return get_class( $cb ) . '::__invoke';
    return 'unknown';
}
function k20_p16_stats( $s ) {
    $s=(string)$s;
    return array(
      'len'=>strlen($s),
      'sha256'=>hash('sha256',$s),
      'has_deep'=>false !== strpos($s,'بازبینی عمیق فنی'),
      'has_policy'=>false !== strpos($s,'/editorial-policy/'),
      'has_box_shadow'=>false !== strpos($s,'box-shadow'),
      'editorial_count'=>substr_count($s,'نظر کارشناسی کشاورز بیست')
    );
}
add_action( 'rest_api_init', function () {
 register_rest_route('k20-diag/v1','/phase16-filter-isolation',array(
  'methods'=>WP_REST_Server::READABLE,
  'permission_callback'=>function(){return current_user_can('manage_options');},
  'callback'=>function(){
    global $wp_filter,$post;
    $pid=145235;
    $target=get_post($pid);
    if(!$target)return new WP_Error('missing_post','target post missing');
    $old_post=$post;
    $post=$target;
    setup_postdata($post);
    $raw=(string)$target->post_content;
    $baseline=apply_filters('the_content',$raw);
    $rows=array();
    $wanted=array(
      'Elementor\\Frontend::apply_builder_in_content',
      'IRK_Next_Shopping::content',
      'ElementorPro\\Modules\\ThemeBuilder\\Classes\\Locations_Manager::builder_wrapper'
    );
    if(!empty($wp_filter['the_content']) && is_object($wp_filter['the_content'])){
      foreach($wp_filter['the_content']->callbacks as $priority=>$group){
        foreach($group as $entry){
          if(empty($entry['function']))continue;
          $cb=$entry['function'];
          $n=k20_p16_cb_name($cb);
          if(!in_array($n,$wanted,true))continue;
          $accepted=isset($entry['accepted_args'])?(int)$entry['accepted_args']:1;
          remove_filter('the_content',$cb,$priority);
          try{
            $without=apply_filters('the_content',$raw);
            $rows[]=array('callback'=>$n,'priority'=>(int)$priority,'without'=>k20_p16_stats($without));
          }finally{
            add_filter('the_content',$cb,$priority,$accepted);
          }
        }
      }
    }
    wp_reset_postdata();
    $post=$old_post;
    return rest_ensure_response(array(
      'raw'=>k20_p16_stats($raw),
      'baseline'=>k20_p16_stats($baseline),
      'isolations'=>$rows
    ));
  }
 ));
});
'''
created=None
try:
 r=S.post(SNIP,json={"name":name,"code":code,"scope":"global","active":True,"priority":10,"tags":["k20","temporary","phase16"]},timeout=45)
 r.raise_for_status(); o=r.json(); created=int(o.get("id") or (o.get("snippet") or {}).get("id") or 0)
 if not created: raise RuntimeError("missing temporary snippet id")
 time.sleep(2)
 d=S.get(BASE+"/wp-json/k20-diag/v1/phase16-filter-isolation",timeout=90); d.raise_for_status()
 actual=S.get(BASE+"/wp-json/wp/v2/posts/145235",params={"context":"edit","_fields":"id,content"},timeout=90); actual.raise_for_status()
 rendered=((actual.json().get("content") or {}).get("rendered") or "")
 def stats(x):
  return {"len":len(x.encode("utf-8")),"sha256":hashlib.sha256(x.encode("utf-8")).hexdigest(),"has_deep":"بازبینی عمیق فنی" in x,"has_policy":"/editorial-policy/" in x,"has_box_shadow":"box-shadow" in x,"editorial_count":x.count("نظر کارشناسی کشاورز بیست")}
 print(json.dumps({"ok":True,"temp_id":created,"diagnostic":d.json(),"actual_rest_rendered":stats(rendered)},ensure_ascii=False))
finally:
 if created:
  try:S.delete(f"{SNIP}/{created}",timeout=45)
  except Exception as e:print(json.dumps({"cleanup_warning":str(e)[:300]},ensure_ascii=False))
