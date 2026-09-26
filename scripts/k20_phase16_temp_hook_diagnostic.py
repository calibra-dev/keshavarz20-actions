#!/usr/bin/env python3
import os,json,requests,time

BASE=os.environ["WP_BASE_URL"].rstrip("/")
AUTH=(os.environ["WP_USERNAME"],os.environ["WP_APP_PASSWORD"])
S=requests.Session(); S.auth=AUTH
SNIP=BASE+"/wp-json/code-snippets/v1/snippets"
name="K20 TEMP Phase16 Hook Diagnostic"
code=r'''
if ( ! defined( 'ABSPATH' ) ) { exit; }

function k20_p16_diag_callback_meta( $cb ) {
    $name = '';
    $file = '';
    $line = 0;
    try {
        if ( is_string( $cb ) ) {
            $name = $cb;
            if ( function_exists( $cb ) ) {
                $r = new ReflectionFunction( $cb );
                $file = (string) $r->getFileName();
                $line = (int) $r->getStartLine();
            }
        } elseif ( $cb instanceof Closure ) {
            $name = 'Closure';
            $r = new ReflectionFunction( $cb );
            $file = (string) $r->getFileName();
            $line = (int) $r->getStartLine();
        } elseif ( is_array( $cb ) && count( $cb ) >= 2 ) {
            $left = is_object( $cb[0] ) ? get_class( $cb[0] ) : (string) $cb[0];
            $name = $left . '::' . (string) $cb[1];
            $r = new ReflectionMethod( $cb[0], $cb[1] );
            $file = (string) $r->getFileName();
            $line = (int) $r->getStartLine();
        } elseif ( is_object( $cb ) && method_exists( $cb, '__invoke' ) ) {
            $name = get_class( $cb ) . '::__invoke';
            $r = new ReflectionMethod( $cb, '__invoke' );
            $file = (string) $r->getFileName();
            $line = (int) $r->getStartLine();
        }
    } catch ( Throwable $e ) {
        $name = $name ?: 'unresolved';
    }

    if ( $file ) {
        $norm = str_replace( '\\', '/', $file );
        $pos = strpos( $norm, '/wp-content/' );
        if ( false !== $pos ) {
            $file = substr( $norm, $pos + 1 );
        } else {
            $pos = strpos( $norm, '/wp-includes/' );
            $file = false !== $pos ? substr( $norm, $pos + 1 ) : basename( $norm );
        }
    }
    return array( 'callback' => $name, 'file' => $file, 'line' => $line );
}

function k20_p16_diag_hook_rows( $hook_name ) {
    global $wp_filter;
    $rows = array();
    if ( empty( $wp_filter[ $hook_name ] ) || ! is_object( $wp_filter[ $hook_name ] ) ) {
        return $rows;
    }
    $callbacks = $wp_filter[ $hook_name ]->callbacks;
    foreach ( $callbacks as $priority => $group ) {
        foreach ( $group as $entry ) {
            if ( empty( $entry['function'] ) ) { continue; }
            $meta = k20_p16_diag_callback_meta( $entry['function'] );
            $meta['priority'] = (int) $priority;
            $meta['accepted_args'] = isset( $entry['accepted_args'] ) ? (int) $entry['accepted_args'] : null;
            $rows[] = $meta;
        }
    }
    return $rows;
}

add_action( 'rest_api_init', function () {
    register_rest_route( 'k20-diag/v1', '/phase16-hooks', array(
        'methods' => WP_REST_Server::READABLE,
        'permission_callback' => function () { return current_user_can( 'manage_options' ); },
        'callback' => function () {
            return rest_ensure_response( array(
                'the_content' => k20_p16_diag_hook_rows( 'the_content' ),
                'rest_prepare_post' => k20_p16_diag_hook_rows( 'rest_prepare_post' ),
                'the_posts' => k20_p16_diag_hook_rows( 'the_posts' ),
                'posts_results' => k20_p16_diag_hook_rows( 'posts_results' ),
                'content_save_pre' => k20_p16_diag_hook_rows( 'content_save_pre' ),
                'wp_insert_post_data' => k20_p16_diag_hook_rows( 'wp_insert_post_data' ),
            ) );
        },
    ) );
} );
'''

created_id=None
try:
    payload={"name":name,"code":code,"scope":"global","active":True,"priority":10,"tags":["k20","temporary","phase16"]}
    r=S.post(SNIP,json=payload,timeout=45)
    r.raise_for_status()
    obj=r.json()
    created_id=int(obj.get("id") or (obj.get("snippet") or {}).get("id") or 0)
    if not created_id:
        raise RuntimeError("temporary snippet created but id missing")
    time.sleep(2)
    d=S.get(BASE+"/wp-json/k20-diag/v1/phase16-hooks",timeout=45)
    d.raise_for_status()
    data=d.json()
    print(json.dumps({"ok":True,"temporary_snippet_id":created_id,"hooks":data},ensure_ascii=False))
finally:
    if created_id:
        try:
            S.delete(f"{SNIP}/{created_id}",timeout=45)
        except Exception as e:
            print(json.dumps({"cleanup_warning":str(e)[:300]},ensure_ascii=False))
