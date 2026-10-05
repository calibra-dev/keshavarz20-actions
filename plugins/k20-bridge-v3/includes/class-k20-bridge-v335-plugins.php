<?php
if (!defined('ABSPATH')) exit;

final class K20_Bridge_V335_Plugins {
    private const MAX_FILES=500;

    public static function inventory(): array {
        self::ensure_api();
        $plugins=get_plugins();
        $active=(array)get_option('active_plugins',[]);
        $network=is_multisite()?(array)get_site_option('active_sitewide_plugins',[]):[];
        $updates=get_site_transient('update_plugins');
        $rows=[];
        foreach ($plugins as $basename=>$data) {
            $update=(is_object($updates) && isset($updates->response[$basename]) && is_object($updates->response[$basename]))?$updates->response[$basename]:null;
            $rows[]=[
                'plugin'=>$basename,
                'slug'=>self::slug($basename),
                'name'=>sanitize_text_field((string)($data['Name']??$basename)),
                'version'=>sanitize_text_field((string)($data['Version']??'')),
                'active'=>in_array($basename,$active,true),
                'network_active'=>isset($network[$basename]),
                'requires_wp'=>sanitize_text_field((string)($data['RequiresWP']??'')),
                'requires_php'=>sanitize_text_field((string)($data['RequiresPHP']??'')),
                'text_domain'=>sanitize_key((string)($data['TextDomain']??'')),
                'update_available'=>$update!==null,
                'new_version'=>$update && isset($update->new_version)?sanitize_text_field((string)$update->new_version):null,
            ];
        }
        usort($rows,fn($a,$b)=>strcasecmp((string)$a['name'],(string)$b['name']));
        return [
            'installed'=>count($rows),
            'active'=>count(array_filter($rows,fn($r)=>!empty($r['active']) || !empty($r['network_active']))),
            'plugins'=>$rows,
        ];
    }

    public static function inspect(array $body) {
        $r=self::resolve($body);
        if (is_wp_error($r)) return $r;
        [$basename,$data,$main,$root]=$r;
        $active=(array)get_option('active_plugins',[]);
        $network=is_multisite()?(array)get_site_option('active_sitewide_plugins',[]):[];
        $updates=get_site_transient('update_plugins');
        $update=(is_object($updates) && isset($updates->response[$basename]) && is_object($updates->response[$basename]))?$updates->response[$basename]:null;
        $summary=self::summary($root,$main);
        $routes=self::owned_routes($root,$main,150);

        return [
            'plugin'=>$basename,
            'slug'=>self::slug($basename),
            'name'=>sanitize_text_field((string)($data['Name']??$basename)),
            'version'=>sanitize_text_field((string)($data['Version']??'')),
            'active'=>in_array($basename,$active,true),
            'network_active'=>isset($network[$basename]),
            'requires_wp'=>sanitize_text_field((string)($data['RequiresWP']??'')),
            'requires_php'=>sanitize_text_field((string)($data['RequiresPHP']??'')),
            'text_domain'=>sanitize_key((string)($data['TextDomain']??'')),
            'main_file'=>$basename,
            'main_bytes'=>is_file($main)?(int)filesize($main):null,
            'main_sha256'=>is_file($main)?hash_file('sha256',$main):null,
            'file_count'=>$summary['file_count'],
            'total_bytes'=>$summary['total_bytes'],
            'extensions'=>$summary['extensions'],
            'rest_route_count'=>count($routes),
            'rest_routes'=>$routes,
            'update_available'=>$update!==null,
            'new_version'=>$update && isset($update->new_version)?sanitize_text_field((string)$update->new_version):null,
        ];
    }

    public static function assets(array $body) {
        $r=self::resolve($body);
        if (is_wp_error($r)) return $r;
        [$basename,$data,$main,$root]=$r;
        $files=[];
        foreach (self::files($root,$main,self::MAX_FILES) as [$rel,$full]) {
            if (!self::safe_rel($rel)) continue;
            $files[]=[
                'path'=>$rel,
                'bytes'=>(int)filesize($full),
                'sha256'=>hash_file('sha256',$full),
            ];
        }
        return [
            'plugin'=>$basename,
            'version'=>sanitize_text_field((string)($data['Version']??'')),
            'file_count'=>count($files),
            'truncated'=>count($files)>=self::MAX_FILES,
            'files'=>$files,
        ];
    }

    public static function rest_routes(array $body): array {
        $p=self::payload($body);
        $needle=trim((string)($p['plugin']??''));
        $filter=null;
        if ($needle!=='') {
            $r=self::resolve($body);
            if (is_wp_error($r)) return ['count'=>0,'plugin'=>null,'routes'=>[],'error'=>$r->get_error_code()];
            $filter=['plugin'=>$r[0],'root'=>$r[3],'main'=>$r[2]];
        }
        $out=[];
        foreach (rest_get_server()->get_routes() as $path=>$endpoints) {
            $owners=self::route_owners((array)$endpoints);
            if (!$owners) continue;
            if ($filter && !self::matches($owners,$filter['root'],$filter['main'])) continue;
            $methods=[];
            foreach ((array)$endpoints as $ep) foreach ((array)($ep['methods']??[]) as $method=>$enabled) if ($enabled) $methods[]=(string)$method;
            $methods=array_values(array_unique($methods));
            sort($methods);
            $out[]=[
                'path'=>(string)$path,
                'methods'=>$methods,
                'plugins'=>array_values(array_unique(array_map(fn($o)=>$o['plugin'],$owners))),
            ];
            if (count($out)>=500) break;
        }
        return [
            'count'=>count($out),
            'plugin'=>$filter['plugin']??null,
            'truncated'=>count($out)>=500,
            'routes'=>$out,
        ];
    }

    private static function resolve(array $body) {
        self::ensure_api();
        $p=self::payload($body);
        $needle=trim((string)($p['plugin']??''));
        if ($needle==='') return new WP_Error('plugin_required','payload.plugin is required.',['status'=>400]);
        $plugins=get_plugins();
        if (isset($plugins[$needle])) return self::tuple($needle,$plugins[$needle]);
        $matches=[];
        foreach ($plugins as $basename=>$data) {
            if (strcasecmp(self::slug($basename),$needle)===0 || strcasecmp((string)($data['Name']??''),$needle)===0) $matches[$basename]=$data;
        }
        if (!$matches) return new WP_Error('plugin_not_found','Installed plugin was not found.',['status'=>404]);
        if (count($matches)!==1) return new WP_Error('plugin_ambiguous','Plugin identifier is ambiguous; use exact plugin basename.',['status'=>409]);
        $basename=array_key_first($matches);
        return self::tuple($basename,$matches[$basename]);
    }

    private static function tuple(string $basename,array $data) {
        $base=realpath(WP_PLUGIN_DIR);
        $main=realpath(WP_PLUGIN_DIR.'/'.$basename);
        if (!$base || !$main) return new WP_Error('plugin_path_invalid','Plugin path could not be resolved.',['status'=>409]);
        $norm_base=rtrim(str_replace('\\','/',$base),'/').'/';
        $norm_main=str_replace('\\','/',$main);
        if (!str_starts_with($norm_main,$norm_base)) return new WP_Error('plugin_path_invalid','Plugin path escapes plugin directory.',['status'=>409]);
        $dir=dirname($main);
        $root=$dir===$base?$main:$dir;
        return [$basename,$data,$main,$root];
    }

    private static function payload(array $body): array {
        return is_array($body['payload']??null)?$body['payload']:[];
    }

    private static function ensure_api(): void {
        if (!function_exists('get_plugins')) require_once ABSPATH.'wp-admin/includes/plugin.php';
    }

    private static function slug(string $basename): string {
        $dir=dirname($basename);
        return $dir!=='.'?$dir:(string)preg_replace('/\.php$/i','',basename($basename));
    }

    private static function summary(string $root,string $main): array {
        $n=0;$bytes=0;$ext=[];
        foreach (self::files($root,$main,2000) as [$rel,$full]) {
            if (!self::safe_rel($rel)) continue;
            $n++;$bytes+=(int)filesize($full);
            $e=strtolower(pathinfo($rel,PATHINFO_EXTENSION));
            if ($e!=='') $ext[$e]=($ext[$e]??0)+1;
        }
        ksort($ext);
        return ['file_count'=>$n,'total_bytes'=>$bytes,'extensions'=>$ext];
    }

    private static function files(string $root,string $main,int $max): iterable {
        if (is_file($root)) {
            yield [basename($main),$main];
            return;
        }
        $base=realpath($root);
        if (!$base) return;
        $seen=0;
        $it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($base,FilesystemIterator::SKIP_DOTS));
        foreach ($it as $file) {
            if (!$file->isFile()) continue;
            if (++$seen>$max) break;
            $full=$file->getPathname();
            $rel=ltrim(str_replace(str_replace('\\','/',$base),'',str_replace('\\','/',$full)),'/');
            yield [$rel,$full];
        }
    }

    private static function safe_rel(string $rel): bool {
        $l=strtolower(str_replace('\\','/',$rel));
        foreach (['.env','wp-config','secret','credential','password','private-key','private_key','token','uploads/','cache/','backup','error_log','.log','.sql'] as $deny) {
            if (str_contains($l,$deny)) return false;
        }
        return true;
    }

    private static function owned_routes(string $root,string $main,int $limit): array {
        $out=[];
        foreach (rest_get_server()->get_routes() as $path=>$endpoints) {
            $owners=self::route_owners((array)$endpoints);
            if (!$owners || !self::matches($owners,$root,$main)) continue;
            $methods=[];
            foreach ((array)$endpoints as $ep) foreach ((array)($ep['methods']??[]) as $m=>$enabled) if ($enabled) $methods[]=(string)$m;
            $methods=array_values(array_unique($methods)); sort($methods);
            $out[]=['path'=>(string)$path,'methods'=>$methods];
            if (count($out)>=$limit) break;
        }
        return $out;
    }

    private static function route_owners(array $endpoints): array {
        $out=[];
        foreach ($endpoints as $ep) {
            $file=self::callback_file($ep['callback']??null);
            if (!$file) continue;
            $plugin=self::plugin_for_file($file);
            if ($plugin) $out[]=['plugin'=>$plugin,'file'=>$file];
        }
        return $out;
    }

    private static function callback_file($cb): ?string {
        try {
            if ($cb instanceof Closure) return (new ReflectionFunction($cb))->getFileName()?:null;
            if (is_string($cb) && function_exists($cb)) return (new ReflectionFunction($cb))->getFileName()?:null;
            if (is_array($cb) && count($cb)>=2) return (new ReflectionMethod($cb[0],$cb[1]))->getFileName()?:null;
            if (is_object($cb) && is_callable($cb)) return (new ReflectionMethod($cb,'__invoke'))->getFileName()?:null;
        } catch (Throwable $e) {}
        return null;
    }

    private static function plugin_for_file(string $file): ?string {
        self::ensure_api();
        $base=realpath(WP_PLUGIN_DIR);
        $real=realpath($file);
        if (!$base || !$real) return null;
        $norm_base=rtrim(str_replace('\\','/',$base),'/').'/';
        $norm_real=str_replace('\\','/',$real);
        if (!str_starts_with($norm_real,$norm_base)) return null;
        foreach (get_plugins() as $basename=>$data) {
            $main=realpath(WP_PLUGIN_DIR.'/'.$basename);
            if (!$main) continue;
            $dir=dirname($main);
            if ($dir===$base) {
                if ($real===$main) return $basename;
            } elseif ($real===$main || str_starts_with($real,$dir.DIRECTORY_SEPARATOR)) {
                return $basename;
            }
        }
        return null;
    }

    private static function matches(array $owners,string $root,string $main): bool {
        $rr=realpath($root); $mr=realpath($main);
        foreach ($owners as $o) {
            $f=realpath((string)($o['file']??''));
            if (!$f) continue;
            if ($rr && is_dir($rr) && str_starts_with($f,$rr.DIRECTORY_SEPARATOR)) return true;
            if ($mr && $f===$mr) return true;
        }
        return false;
    }
}
