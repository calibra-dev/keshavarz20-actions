<?php
if (!defined('ABSPATH')) exit;

/**
 * Narrow, reversible performance guard for the drip-tape calculator.
 * Scope is intentionally limited to post 143698 and does not remove
 * WooCommerce, IranKala, Digits, WhatsApp or jQuery functionality.
 */
final class K20_Bridge_V33_Performance {
    private const TARGET_POST_ID = 143698;
    private const LCP_ATTACHMENT_ID = 145308;
    private const LCP_672_ATTACHMENT_ID = 146333;

    public static function boot(): void {
        add_filter('wp_calculate_image_srcset', [__CLASS__, 'lcp_srcset'], 20, 5);
        add_filter('wp_calculate_image_sizes', [__CLASS__, 'lcp_sizes'], 20, 5);
        add_filter('script_loader_tag', [__CLASS__, 'script_priority'], 20, 3);
        add_action('wp_enqueue_scripts', [__CLASS__, 'dequeue_irrelevant_assets'], 999);
    }

    private static function is_target(): bool {
        return !is_admin()
            && is_singular('post')
            && (int) get_queried_object_id() === self::TARGET_POST_ID;
    }

    public static function lcp_srcset($sources, $size_array, $image_src, $image_meta, $attachment_id) {
        if (!self::is_target() || (int) $attachment_id !== self::LCP_ATTACHMENT_ID || !is_array($sources)) {
            return $sources;
        }

        $candidate = wp_get_attachment_image_src(self::LCP_672_ATTACHMENT_ID, 'full');
        if (is_array($candidate) && !empty($candidate[0]) && (int) ($candidate[1] ?? 0) === 672) {
            $sources[672] = [
                'url' => esc_url_raw((string) $candidate[0]),
                'descriptor' => 'w',
                'value' => 672,
            ];
            ksort($sources, SORT_NUMERIC);
        }

        return $sources;
    }

    public static function lcp_sizes($sizes, $size, $image_src, $image_meta, $attachment_id) {
        if (!self::is_target() || (int) $attachment_id !== self::LCP_ATTACHMENT_ID) {
            return $sizes;
        }

        // Actual mobile content width is viewport minus the 20px gutters on each side.
        return '(max-width: 767px) calc(100vw - 40px), (max-width: 1200px) 100vw, 1200px';
    }

    public static function script_priority(string $tag, string $handle, string $src): string {
        if (!self::is_target() || $handle !== 'google-tag-manager') {
            return $tag;
        }

        if (stripos($tag, 'fetchpriority=') === false) {
            $tag = preg_replace('/<script\b/i', '<script fetchpriority="low"', $tag, 1) ?: $tag;
        }
        return $tag;
    }

    public static function dequeue_irrelevant_assets(): void {
        if (!self::is_target()) return;

        // Front-end payment gateway help-link CSS is not used by the calculator.
        // This is deliberately the only dequeue in phase 1.
        wp_dequeue_style('help_style');
    }
}

K20_Bridge_V33_Performance::boot();
