<?php

if (!defined('ABSPATH')) {
    exit;
}

final class K20_Bridge_V31_Content {
    private const MAX_PATTERN = 20000;
    private const MAX_REPLACEMENT = 250000;
    private const MAX_MATCHES = 50;

    public static function search(array $body) {
        $payload = is_array($body['payload'] ?? null) ? $body['payload'] : [];
        $target = strtolower((string) ($payload['target_type'] ?? 'post'));
        $post_id = absint($payload['post_id'] ?? ($body['id'] ?? 0));
        $pattern = (string) ($payload['pattern'] ?? '');
        $context = max(20, min(300, (int) ($payload['context'] ?? 100)));

        if ($pattern === '' || strlen($pattern) > self::MAX_PATTERN) {
            return new WP_Error('invalid_pattern', 'A non-empty bounded search pattern is required.', ['status' => 400]);
        }

        $source = self::read_target($target, $post_id, $payload);
        if (is_wp_error($source)) {
            return $source;
        }

        $text = $source['value'];
        $matches = [];
        $offset = 0;
        while (($pos = strpos($text, $pattern, $offset)) !== false && count($matches) < self::MAX_MATCHES) {
            $start = max(0, $pos - $context);
            $length = min(strlen($text) - $start, strlen($pattern) + ($context * 2));
            $matches[] = [
                'offset' => $pos,
                'snippet' => substr($text, $start, $length),
            ];
            $offset = $pos + max(1, strlen($pattern));
        }

        return [
            'post_id' => $post_id,
            'target_type' => $target,
            'field' => $source['field'],
            'matches' => substr_count($text, $pattern),
            'returned' => count($matches),
            'sha256' => hash('sha256', $text),
            'snippets' => $matches,
        ];
    }

    public static function patch(array $body, bool $dry_run) {
        $payload = is_array($body['payload'] ?? null) ? $body['payload'] : [];
        $target = strtolower((string) ($payload['target_type'] ?? 'post'));
        $post_id = absint($payload['post_id'] ?? ($body['id'] ?? 0));
        $old = (string) ($payload['old_content'] ?? '');
        $new = (string) ($payload['new_content'] ?? '');
        $replace_all = !empty($payload['replace_all']);
        $expected_sha = strtolower((string) ($payload['expected_sha256'] ?? ''));

        if ($old === '' || strlen($old) > self::MAX_PATTERN) {
            return new WP_Error('invalid_old_content', 'old_content must be non-empty and bounded.', ['status' => 400]);
        }
        if (strlen($new) > self::MAX_REPLACEMENT) {
            return new WP_Error('replacement_too_large', 'new_content exceeds the allowed size.', ['status' => 400]);
        }

        $source = self::read_target($target, $post_id, $payload);
        if (is_wp_error($source)) {
            return $source;
        }

        $current = $source['value'];
        $sha = hash('sha256', $current);
        if ($expected_sha !== '' && !hash_equals($expected_sha, $sha)) {
            return new WP_Error('stale_content', 'Target content changed since it was inspected.', ['status' => 409]);
        }

        $count = substr_count($current, $old);
        if ($count === 0) {
            return new WP_Error('no_match', 'old_content was not found.', ['status' => 409]);
        }
        if (!$replace_all && $count !== 1) {
            return new WP_Error('multiple_matches', 'old_content matched more than once; add context or set replace_all.', ['status' => 409]);
        }

        $updated = str_replace($old, $new, $current, $replaced);
        if (!$replace_all && $replaced !== 1) {
            return new WP_Error('replace_mismatch', 'Exact replacement count was not one.', ['status' => 409]);
        }

        if ($target === 'meta' && $source['field'] === '_elementor_data') {
            json_decode($updated, true);
            if (json_last_error() !== JSON_ERROR_NONE) {
                return new WP_Error('invalid_elementor_json', 'Patch would make Elementor JSON invalid.', ['status' => 400]);
            }
        }

        $plan = [
            'post_id' => $post_id,
            'target_type' => $target,
            'field' => $source['field'],
            'matches' => $count,
            'changed' => $replace_all ? $replaced : 1,
            'before_sha256' => $sha,
            'after_sha256' => hash('sha256', $updated),
        ];
        if ($dry_run) {
            $plan['planned'] = true;
            return $plan;
        }

        $saved = self::write_target($target, $post_id, $source['field'], $updated);
        if (is_wp_error($saved)) {
            return $saved;
        }

        if ($target === 'meta' && $source['field'] === '_elementor_data') {
            self::clear_elementor_cache();
        }
        return $plan;
    }

    public static function elementor_inspect(int $id) {
        if (!$id || !get_post($id)) {
            return new WP_Error('not_found', 'Post not found.', ['status' => 404]);
        }
        $data = get_post_meta($id, '_elementor_data', true);
        return [
            'id' => $id,
            'edit_mode' => get_post_meta($id, '_elementor_edit_mode', true),
            'template_type' => get_post_meta($id, '_elementor_template_type', true),
            'elementor_version' => get_post_meta($id, '_elementor_version', true),
            'data_present' => $data !== '' && $data !== null,
            'data_bytes' => is_string($data) ? strlen($data) : strlen(wp_json_encode($data)),
            'sha256' => hash('sha256', is_string($data) ? $data : wp_json_encode($data)),
        ];
    }

    public static function elementor_search(array $body) {
        $payload = is_array($body['payload'] ?? null) ? $body['payload'] : [];
        $payload['target_type'] = 'meta';
        $payload['meta_key'] = '_elementor_data';
        $payload['post_id'] = absint($payload['post_id'] ?? ($body['id'] ?? 0));
        $body['payload'] = $payload;
        return self::search($body);
    }

    public static function elementor_edit(array $body, bool $dry_run) {
        $payload = is_array($body['payload'] ?? null) ? $body['payload'] : [];
        $payload['target_type'] = 'meta';
        $payload['meta_key'] = '_elementor_data';
        $payload['post_id'] = absint($payload['post_id'] ?? ($body['id'] ?? 0));
        $body['payload'] = $payload;
        return self::patch($body, $dry_run);
    }

    private static function read_target(string $target, int $post_id, array $payload) {
        $post = $post_id ? get_post($post_id) : null;
        if (!$post) {
            return new WP_Error('not_found', 'Post not found.', ['status' => 404]);
        }

        if ($target === 'post') {
            $field = (string) ($payload['field'] ?? 'post_content');
            if (!in_array($field, ['post_content','post_excerpt','post_title'], true)) {
                return new WP_Error('field_not_allowed', 'Post field is not allow-listed.', ['status' => 400]);
            }
            return ['field' => $field, 'value' => (string) $post->{$field}];
        }

        if ($target === 'meta') {
            $meta_key = (string) ($payload['meta_key'] ?? '');
            if (!in_array($meta_key, ['_elementor_data'], true)) {
                return new WP_Error('meta_not_allowed', 'Meta key is not allow-listed for content patching.', ['status' => 400]);
            }
            $value = get_post_meta($post_id, $meta_key, true);
            return ['field' => $meta_key, 'value' => is_string($value) ? $value : wp_json_encode($value)];
        }

        return new WP_Error('target_not_allowed', 'target_type must be post or meta.', ['status' => 400]);
    }

    private static function write_target(string $target, int $post_id, string $field, string $value) {
        if ($target === 'post') {
            $result = wp_update_post(['ID' => $post_id, $field => $value], true);
            return is_wp_error($result) ? $result : true;
        }
        if ($target === 'meta') {
            update_post_meta($post_id, $field, wp_slash($value));
            return true;
        }
        return new WP_Error('target_not_allowed', 'Unsupported target.', ['status' => 400]);
    }

    private static function clear_elementor_cache(): void {
        if (class_exists('Elementor\\Plugin') && method_exists('Elementor\\Plugin', 'instance')) {
            $plugin = \Elementor\Plugin::instance();
            if (isset($plugin->files_manager) && method_exists($plugin->files_manager, 'clear_cache')) {
                $plugin->files_manager->clear_cache();
            }
        }
        if (function_exists('wp_cache_flush')) {
            wp_cache_flush();
        }
    }
}
