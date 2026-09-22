<?php
if (!defined('ABSPATH')) exit;

final class K20_Bridge_V32_Updater {
    private const MANIFEST_URL='https://raw.githubusercontent.com/calibra-dev/keshavarz20-actions/main/plugins/k20-bridge-v3/update-manifest.json';
    private const REPO_RELEASE_PREFIX='https://github.com/calibra-dev/keshavarz20-actions/releases/download/';
    private const BACKUP_OPTION='k20_bridge_v32_last_backup';
    private const PENDING_OPTION='k20_bridge_v32_pending_update';

    public static function boot(): void {
        $pending=get_option(self::PENDING_OPTION,[]);
        if (!is_array($pending) || empty($pending['expected_version'])) return;
        if (defined('K20_BRIDGE_RUNTIME_VERSION') && K20_BRIDGE_RUNTIME_VERSION===$pending['expected_version']) {
            delete_option(self::PENDING_OPTION);
        }
    }

    public static function check() {
        $manifest=self::manifest();
        if (is_wp_error($manifest)) return $manifest;
        $current=defined('K20_BRIDGE_RUNTIME_VERSION')?K20_BRIDGE_RUNTIME_VERSION:'0.0.0';
        return [
            'current_version'=>$current,'available_version'=>$manifest['version'],
            'update_available'=>version_compare($manifest['version'],$current,'>'),
            'package_url'=>$manifest['package_url'],'checksum_url'=>$manifest['checksum_url'],
            'minimum_wp'=>$manifest['minimum_wp']??null,'minimum_php'=>$manifest['minimum_php']??null
        ];
    }

    public static function stage(array $body,bool $dry_run) {
        $manifest=self::manifest(); if (is_wp_error($manifest)) return $manifest;
        if ($dry_run) return ['planned'=>true,'version'=>$manifest['version'],'package_url'=>$manifest['package_url']];
        $upload=wp_upload_dir(); if (!empty($upload['error'])) return new WP_Error('upload_dir_error',$upload['error'],['status'=>500]);
        $dir=trailingslashit($upload['basedir']).'k20-bridge-staging';
        if (!wp_mkdir_p($dir)) return new WP_Error('staging_dir_failed','Could not create staging directory.',['status'=>500]);
        $zip=$dir.'/k20-bridge-'.$manifest['version'].'.zip';
        $sum=$dir.'/k20-bridge-'.$manifest['version'].'.sha256';

        $r=self::download_to($manifest['package_url'],$zip); if (is_wp_error($r)) return $r;
        $r=self::download_to($manifest['checksum_url'],$sum); if (is_wp_error($r)) { @unlink($zip); return $r; }
        $line=trim((string)@file_get_contents($sum));
        if (!preg_match('/^([a-f0-9]{64})\b/i',$line,$m)) { @unlink($zip); @unlink($sum); return new WP_Error('invalid_checksum','Release checksum file is invalid.',['status'=>502]); }
        $actual=hash_file('sha256',$zip);
        if (!hash_equals(strtolower($m[1]),strtolower($actual))) { @unlink($zip); @unlink($sum); return new WP_Error('checksum_mismatch','Downloaded package checksum mismatch.',['status'=>409]); }
        update_option('k20_bridge_v32_staged',['version'=>$manifest['version'],'zip'=>$zip,'sha256'=>$actual,'staged_at_utc'=>gmdate('c')],false);
        return ['staged'=>true,'version'=>$manifest['version'],'sha256'=>$actual,'bytes'=>filesize($zip)];
    }

    public static function apply(array $body,bool $dry_run) {
        $staged=get_option('k20_bridge_v32_staged',[]);
        if (!is_array($staged) || empty($staged['zip']) || !is_file($staged['zip'])) return new WP_Error('update_not_staged','No verified update package is staged.',['status'=>409]);
        if ($dry_run) return ['planned'=>true,'version'=>$staged['version'],'sha256'=>$staged['sha256']];

        require_once ABSPATH.'wp-admin/includes/file.php';
        $upload=wp_upload_dir(); if (!empty($upload['error'])) return new WP_Error('upload_dir_error',$upload['error'],['status'=>500]);
        $work=trailingslashit($upload['basedir']).'k20-bridge-staging/unpack-'.wp_generate_uuid4();
        if (!wp_mkdir_p($work)) return new WP_Error('unpack_dir_failed','Could not create unpack directory.',['status'=>500]);
        $unz=unzip_file($staged['zip'],$work);
        if (is_wp_error($unz)) { self::rm_tree($work); return $unz; }
        $source=trailingslashit($work).'k20-bridge-v3';
        $main=trailingslashit($source).'k20-bridge-v3.php';
        if (!is_file($main)) { self::rm_tree($work); return new WP_Error('package_shape_invalid','Package does not contain the expected plugin folder.',['status'=>409]); }
        $version=self::read_version($main);
        if ($version!==$staged['version']) { self::rm_tree($work); return new WP_Error('package_version_mismatch','Package version does not match staged manifest.',['status'=>409]); }

        $plugin_dir=dirname(__DIR__);
        $backup_root=trailingslashit($upload['basedir']).'k20-bridge-backups';
        wp_mkdir_p($backup_root);
        $backup=$backup_root.'/v'.(defined('K20_BRIDGE_RUNTIME_VERSION')?K20_BRIDGE_RUNTIME_VERSION:'unknown').'-'.gmdate('Ymd-His');
        if (!self::copy_tree($plugin_dir,$backup)) { self::rm_tree($work); return new WP_Error('backup_failed','Could not create plugin backup.',['status'=>500]); }

        if (!self::copy_tree($source,$plugin_dir)) {
            self::copy_tree($backup,$plugin_dir);
            self::rm_tree($work);
            return new WP_Error('update_copy_failed','Update copy failed and backup was restored.',['status'=>500]);
        }
        $installed=self::read_version($plugin_dir.'/k20-bridge-v3.php');
        if ($installed!==$staged['version']) {
            self::copy_tree($backup,$plugin_dir);
            self::rm_tree($work);
            return new WP_Error('post_copy_verify_failed','Installed file version verification failed; backup restored.',['status'=>500]);
        }

        update_option(self::BACKUP_OPTION,['path'=>$backup,'version'=>defined('K20_BRIDGE_RUNTIME_VERSION')?K20_BRIDGE_RUNTIME_VERSION:null,'created_at_utc'=>gmdate('c')],false);
        update_option(self::PENDING_OPTION,['expected_version'=>$installed,'backup_path'=>$backup,'applied_at_utc'=>gmdate('c')],false);
        self::rm_tree($work);
        return ['applied'=>true,'installed_file_version'=>$installed,'previous_backup'=>basename($backup),'next_request_health_verification'=>true];
    }

    public static function rollback(array $body,bool $dry_run) {
        $last=get_option(self::BACKUP_OPTION,[]);
        if (!is_array($last) || empty($last['path']) || !is_dir($last['path'])) return new WP_Error('backup_not_found','No updater backup is available.',['status'=>404]);
        if ($dry_run) return ['planned'=>true,'backup'=>basename($last['path']),'version'=>$last['version']??null];
        $plugin_dir=dirname(__DIR__);
        if (!self::copy_tree($last['path'],$plugin_dir)) return new WP_Error('rollback_failed','Could not restore bridge backup.',['status'=>500]);
        $version=self::read_version($plugin_dir.'/k20-bridge-v3.php');
        delete_option(self::PENDING_OPTION);
        return ['rolled_back'=>true,'installed_file_version'=>$version,'backup'=>basename($last['path'])];
    }

    private static function manifest() {
        $r=wp_remote_get(self::MANIFEST_URL,['timeout'=>15,'redirection'=>3,'user-agent'=>'Keshavarz20-Bridge-Updater']);
        if (is_wp_error($r)) return $r;
        if ((int)wp_remote_retrieve_response_code($r)!==200) return new WP_Error('manifest_http_error','Update manifest request failed.',['status'=>502]);
        $m=json_decode((string)wp_remote_retrieve_body($r),true);
        if (!is_array($m) || empty($m['version']) || empty($m['package_url']) || empty($m['checksum_url'])) return new WP_Error('manifest_invalid','Update manifest is invalid.',['status'=>502]);
        if (!preg_match('/^\d+\.\d+\.\d+$/',(string)$m['version'])) return new WP_Error('manifest_version_invalid','Manifest version is invalid.',['status'=>502]);
        foreach (['package_url','checksum_url'] as $key) {
            if (!str_starts_with((string)$m[$key],self::REPO_RELEASE_PREFIX)) return new WP_Error('manifest_origin_invalid','Update asset origin is not allow-listed.',['status'=>502]);
        }
        if (!empty($m['minimum_php']) && version_compare(PHP_VERSION,(string)$m['minimum_php'],'<')) return new WP_Error('php_too_old','PHP version is below update minimum.',['status'=>409]);
        if (!empty($m['minimum_wp']) && version_compare(get_bloginfo('version'),(string)$m['minimum_wp'],'<')) return new WP_Error('wp_too_old','WordPress version is below update minimum.',['status'=>409]);
        return $m;
    }

    private static function download_to(string $url,string $dest) {
        $r=wp_remote_get($url,['timeout'=>60,'redirection'=>5,'stream'=>true,'filename'=>$dest,'user-agent'=>'Keshavarz20-Bridge-Updater']);
        if (is_wp_error($r)) return $r;
        $code=(int)wp_remote_retrieve_response_code($r);
        if ($code<200 || $code>=300 || !is_file($dest)) return new WP_Error('download_failed','Release asset download failed.',['status'=>502]);
        return true;
    }
    private static function read_version(string $file): string {
        if (!is_file($file)) return '';
        $head=(string)file_get_contents($file,false,null,0,8192);
        return preg_match('/^[ \t\/*#@]*Version:\s*([0-9.]+)/mi',$head,$m)?trim($m[1]):'';
    }
    private static function copy_tree(string $src,string $dst): bool {
        if (!is_dir($src)) return false;
        if (!is_dir($dst) && !wp_mkdir_p($dst)) return false;
        $it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($src,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::SELF_FIRST);
        foreach ($it as $item) {
            $rel=substr($item->getPathname(),strlen($src)+1); $target=$dst.'/'.$rel;
            if ($item->isDir()) { if (!is_dir($target) && !wp_mkdir_p($target)) return false; }
            else { if (!is_dir(dirname($target))) wp_mkdir_p(dirname($target)); if (!@copy($item->getPathname(),$target)) return false; }
        }
        return true;
    }
    private static function rm_tree(string $dir): void {
        if (!is_dir($dir)) return;
        $it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) { $item->isDir()?@rmdir($item->getPathname()):@unlink($item->getPathname()); }
        @rmdir($dir);
    }
}
add_action('plugins_loaded',['K20_Bridge_V32_Updater','boot'],20);
