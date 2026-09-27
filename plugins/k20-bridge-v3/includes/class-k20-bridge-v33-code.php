<?php
if (!defined('ABSPATH')) exit;

final class K20_Bridge_V33_Code {
    private const MAX_FILE_BYTES=262144;
    private const MAX_SEARCH_FILES=200;
    private const MAX_SEARCH_BYTES=2097152;
    private static array $extensions=['php','js','css','json','html','htm','txt','md','yml','yaml'];

    public static function read(array $body) {
        $p=self::payload($body);
        $resolved=self::resolve((string)($p['root']??'bridge'),(string)($p['path']??''));
        if (is_wp_error($resolved)) return $resolved;
        [$root_key,$root,$path,$full]=$resolved;
        if (!is_file($full)) return new WP_Error('code_file_not_found','Requested file does not exist.',['status'=>404]);
        $bytes=filesize($full);
        if ($bytes>self::MAX_FILE_BYTES) return new WP_Error('code_file_too_large','File exceeds 256 KiB read limit.',['status'=>400]);
        $text=(string)file_get_contents($full);
        return ['root'=>$root_key,'path'=>$path,'bytes'=>$bytes,'sha256'=>hash('sha256',$text),'source_text'=>self::redact($text)];
    }

    public static function search(array $body) {
        $p=self::payload($body);
        $root_key=(string)($p['root']??'bridge');
        $pattern=(string)($p['pattern']??'');
        if ($pattern==='') return new WP_Error('pattern_required','pattern is required.',['status'=>400]);
        if (strlen($pattern)>200) return new WP_Error('pattern_too_long','pattern is too long.',['status'=>400]);
        $roots=self::roots();
        if (!isset($roots[$root_key])) return new WP_Error('code_root_not_allowed','Requested code root is not allow-listed.',['status'=>403]);
        $root=realpath($roots[$root_key]);
        if (!$root || !is_dir($root)) return new WP_Error('code_root_missing','Requested code root is unavailable.',['status'=>404]);

        $limit=max(1,min(100,(int)($p['limit']??30)));
        $items=[];$files_seen=0;$bytes_seen=0;
        $it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root,FilesystemIterator::SKIP_DOTS));
        foreach ($it as $file) {
            if (!$file->isFile()) continue;
            if (++$files_seen>self::MAX_SEARCH_FILES) break;
            $full=$file->getPathname();
            $rel=ltrim(str_replace(str_replace('\\','/',$root),'',str_replace('\\','/',$full)),'/');
            if (!self::path_allowed($root_key,$rel)) continue;
            $size=$file->getSize();
            if ($size>self::MAX_FILE_BYTES) continue;
            $bytes_seen+=$size;
            if ($bytes_seen>self::MAX_SEARCH_BYTES) break;
            $lines=@file($full,FILE_IGNORE_NEW_LINES);
            if (!is_array($lines)) continue;
            foreach ($lines as $n=>$line) {
                if (stripos($line,$pattern)===false) continue;
                $items[]=['path'=>$rel,'line'=>(int)$n+1,'text'=>self::redact((string)$line)];
                if (count($items)>=$limit) break 2;
            }
        }
        return ['root'=>$root_key,'pattern'=>$pattern,'count'=>count($items),'items'=>$items,'files_scanned'=>$files_seen,'bytes_scanned'=>$bytes_seen];
    }

    private static function resolve(string $root_key,string $path) {
        $roots=self::roots();
        if (!isset($roots[$root_key])) return new WP_Error('code_root_not_allowed','Requested code root is not allow-listed.',['status'=>403]);
        $path=str_replace('\\','/',$path);
        $path=ltrim($path,'/');
        if ($path==='' || str_contains($path,'..') || !self::path_allowed($root_key,$path)) return new WP_Error('code_path_not_allowed','Requested code path is not allow-listed.',['status'=>403]);
        $root=realpath($roots[$root_key]);
        if (!$root) return new WP_Error('code_root_missing','Requested code root is unavailable.',['status'=>404]);
        $candidate=$root.DIRECTORY_SEPARATOR.str_replace('/',DIRECTORY_SEPARATOR,$path);
        $full=realpath($candidate);
        if (!$full || !str_starts_with($full,$root.DIRECTORY_SEPARATOR)) return new WP_Error('code_path_not_allowed','Requested code path escapes the allow-listed root.',['status'=>403]);
        return [$root_key,$root,$path,$full];
    }

    private static function path_allowed(string $root_key,string $path): bool {
        $lower=strtolower(str_replace('\\','/',$path));
        foreach (['.env','wp-config','secret','credential','password','private-key','private_key','token','vendor/','node_modules/','uploads/'] as $deny) {
            if (str_contains($lower,$deny)) return false;
        }
        $ext=strtolower(pathinfo($lower,PATHINFO_EXTENSION));
        if (!in_array($ext,self::$extensions,true)) return false;
        if ($root_key==='mu' && !str_starts_with(basename($lower),'k20-')) return false;
        return true;
    }

    private static function roots(): array {
        $roots=['bridge'=>dirname(__DIR__)];
        $theme=get_stylesheet_directory();
        if (is_string($theme) && $theme!=='') $roots['theme']=$theme;
        if (defined('WPMU_PLUGIN_DIR') && is_dir(WPMU_PLUGIN_DIR)) $roots['mu']=WPMU_PLUGIN_DIR;
        return $roots;
    }

    private static function redact(string $text): string {
        $text=preg_replace('/(define\s*\(\s*[\'"][^\'"]*(?:KEY|SECRET|TOKEN|PASSWORD)[^\'"]*[\'"]\s*,\s*)[\'"][^\'"]*[\'"]/i','$1\'***\'',$text);
        $text=preg_replace('/(\$(?:password|secret|token|api_key|consumer_key|consumer_secret)\s*=\s*)[\'"][^\'"]*[\'"]/i','$1\'***\'',$text);
        return (string)$text;
    }

    private static function payload(array $body): array { return is_array($body['payload']??null)?$body['payload']:[]; }
}
