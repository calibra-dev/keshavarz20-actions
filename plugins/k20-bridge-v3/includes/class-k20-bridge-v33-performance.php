<?php
if (!defined('ABSPATH')) exit;

/**
 * Narrow, reversible performance guard for verified LCP targets.
 * Scope is intentionally limited to the drip-tape calculator and the
 * audited sandy-well filtration article. It does not remove WooCommerce,
 * IranKala, Digits, WhatsApp or jQuery functionality.
 */
final class K20_Bridge_V33_Performance {
    private const TARGET_POST_ID = 143698;
    private const LCP_ATTACHMENT_ID = 145308;
    private const LCP_672_ATTACHMENT_ID = 146333;
    private const LCP_768_ATTACHMENT_ID = 146338;
    private const ARTICLE_POST_ID = 146227;
    private const ARTICLE_LCP_ATTACHMENT_ID = 146240;

    public static function boot(): void {
        add_filter('wp_get_attachment_image_attributes', [__CLASS__, 'lcp_attributes'], 20, 3);
        add_filter('wp_calculate_image_srcset', [__CLASS__, 'lcp_srcset'], 20, 5);
        add_filter('wp_calculate_image_sizes', [__CLASS__, 'lcp_sizes'], 20, 5);
        add_filter('script_loader_tag', [__CLASS__, 'script_priority'], 20, 3);
        add_action('wp_enqueue_scripts', [__CLASS__, 'defer_article_scripts'], 998);
        add_action('wp_enqueue_scripts', [__CLASS__, 'dequeue_irrelevant_assets'], 999);
    }

    private static function is_calculator_target(): bool {
        return !is_admin()
            && is_singular('post')
            && (int) get_queried_object_id() === self::TARGET_POST_ID;
    }

    private static function is_article_target(): bool {
        return !is_admin()
            && is_singular('post')
            && (int) get_queried_object_id() === self::ARTICLE_POST_ID;
    }

    public static function lcp_attributes(array $attr, $attachment, $size): array {
        $attachment_id = is_object($attachment) ? (int) ($attachment->ID ?? 0) : 0;
        $is_calculator_lcp = self::is_calculator_target() && $attachment_id === self::LCP_ATTACHMENT_ID;
        $is_article_lcp = self::is_article_target() && $attachment_id === self::ARTICLE_LCP_ATTACHMENT_ID;
        if (!$is_calculator_lcp && !$is_article_lcp) {
            return $attr;
        }

        // Keep only the verified LCP image discoverable and immediately fetchable.
        $attr['data-no-lazy'] = '1';
        $attr['loading'] = 'eager';
        $attr['fetchpriority'] = 'high';
        $attr['decoding'] = 'async';
        $class_name = $is_article_lcp ? 'k20-article-lcp' : 'k20-calculator-lcp';
        $classes = preg_split('/\s+/', trim((string) ($attr['class'] ?? ''))) ?: [];
        if (!in_array($class_name, $classes, true)) {
            $classes[] = $class_name;
        }
        $attr['class'] = trim(implode(' ', array_filter($classes)));
        return $attr;
    }

    public static function lcp_srcset($sources, $size_array, $image_src, $image_meta, $attachment_id) {
        if (!self::is_calculator_target() || (int) $attachment_id !== self::LCP_ATTACHMENT_ID || !is_array($sources)) {
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

        $candidate_768 = wp_get_attachment_image_src(self::LCP_768_ATTACHMENT_ID, 'full');
        if (is_array($candidate_768) && !empty($candidate_768[0]) && (int) ($candidate_768[1] ?? 0) === 768) {
            // Replace only the 768w source used by high-DPR mobile devices.
            // Desktop/full-size candidates remain untouched.
            $sources[768] = [
                'url' => esc_url_raw((string) $candidate_768[0]),
                'descriptor' => 'w',
                'value' => 768,
            ];
            ksort($sources, SORT_NUMERIC);
        }

        return $sources;
    }

    public static function lcp_sizes($sizes, $size, $image_src, $image_meta, $attachment_id) {
        if (!self::is_calculator_target() || (int) $attachment_id !== self::LCP_ATTACHMENT_ID) {
            return $sizes;
        }

        // Actual mobile content width is viewport minus the 20px gutters on each side.
        return '(max-width: 767px) calc(100vw - 40px), (max-width: 1200px) 100vw, 1200px';
    }

    public static function script_priority(string $tag, string $handle, string $src): string {
        if (!self::is_calculator_target() || $handle !== 'google-tag-manager') {
            return $tag;
        }

        if (stripos($tag, 'fetchpriority=') === false) {
            $tag = preg_replace('/<script\b/i', '<script fetchpriority="low"', $tag, 1) ?: $tag;
        }
        return $tag;
    }

    public static function defer_article_scripts(): void {
        if (!self::is_article_target()) return;

        // Preserve functionality while moving non-critical interactive scripts out of
        // the parser-blocking path for this audited article only. WordPress may adjust
        // the strategy when dependency constraints require a safer execution order.
        foreach (['digits-login-script', 'slick', 'venobox', 'dtwcbe', 'nta-js-popup'] as $handle) {
            if (wp_script_is($handle, 'enqueued')) {
                wp_script_add_data($handle, 'strategy', 'defer');
            }
        }
    }

    public static function dequeue_irrelevant_assets(): void {
        if (!self::is_calculator_target()) return;

        // Front-end payment gateway help-link CSS is not used by the calculator.
        wp_dequeue_style('help_style');

        // Elementor Pro MegaTheme icon font CSS is 100% unused on this calculator page
        // in Lighthouse coverage and has no meaningful class intersection with rendered
        // calculator/header/cart/navigation markup. Keep all IranKala, WooCommerce,
        // Digits and WhatsApp styles intact.
        wp_dequeue_style('mega-theme-icon');
    }
}

K20_Bridge_V33_Performance::boot();
