<?php
if (!defined('ABSPATH')) exit;

/**
 * Narrow, reversible performance guard for verified LCP targets.
 * Scope is intentionally limited to verified page-level targets: the drip-tape
 * calculator, the audited sandy-well filtration article and product canary
 * 134980. It does not remove WooCommerce, IranKala, Digits, WhatsApp, analytics
 * or jQuery functionality globally.
 */
final class K20_Bridge_V33_Performance {
    private const TARGET_POST_ID = 143698;
    private const LCP_ATTACHMENT_ID = 145308;
    private const LCP_672_ATTACHMENT_ID = 146333;
    private const LCP_768_ATTACHMENT_ID = 146338;
    private const ARTICLE_POST_ID = 146227;
    private const ARTICLE_LCP_ATTACHMENT_ID = 146240;
    private const ARTICLE_LCP_672_ATTACHMENT_ID = 146385;
    private const ARTICLE_LCP_768_ATTACHMENT_ID = 146383;
    private const PRODUCT_POST_ID = 134980;
    private const PRODUCT_LCP_ATTACHMENT_ID = 144291;
    private const PRODUCT_MOBILE_LOGO_100_URL = 'https://keshavarz20.com/wp-content/uploads/2025/11/cropped-logo-deks22-keshavarz20-100x100.png';

    public static function boot(): void {
        add_filter('wp_get_attachment_image_attributes', [__CLASS__, 'lcp_attributes'], 20, 3);
        add_filter('wp_calculate_image_srcset', [__CLASS__, 'lcp_srcset'], 20, 5);
        add_filter('wp_calculate_image_sizes', [__CLASS__, 'lcp_sizes'], 20, 5);
        add_filter('script_loader_tag', [__CLASS__, 'script_priority'], 20, 3);
        add_filter('litespeed_buffer_after', [__CLASS__, 'final_html_repairs'], 20, 1);
        add_action('wp', [__CLASS__, 'product_cache_policy'], 20);
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

    private static function is_product_target(): bool {
        return !is_admin()
            && function_exists('is_product')
            && is_product()
            && (int) get_queried_object_id() === self::PRODUCT_POST_ID;
    }

    private static function has_private_commerce_cookie(): bool {
        foreach (array_keys($_COOKIE ?? []) as $name) {
            $name = (string) $name;
            if (str_starts_with($name, 'wp_woocommerce_session_')
                || str_starts_with($name, 'woocommerce_')
                || str_starts_with($name, 'wordpress_logged_in_')) {
                return true;
            }
        }
        return false;
    }

    public static function product_cache_policy(): void {
        if (!self::is_product_target() || is_user_logged_in() || self::has_private_commerce_cookie()) return;
        $method = strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET'));
        if (!in_array($method, ['GET', 'HEAD'], true)) return;
        if (!empty($_GET)) return;

        // Ask LiteSpeed to treat this anonymous canary product as cacheable without
        // forcing a public response for logged-in/cart sessions.
        do_action('litespeed_control_set_cacheable', 'K20 product 134980 anonymous canary');
        do_action('litespeed_control_set_ttl', 300);
    }

    public static function lcp_attributes(array $attr, $attachment, $size): array {
        $attachment_id = is_object($attachment) ? (int) ($attachment->ID ?? 0) : 0;
        $is_calculator_lcp = self::is_calculator_target() && $attachment_id === self::LCP_ATTACHMENT_ID;
        $is_article_lcp = self::is_article_target() && $attachment_id === self::ARTICLE_LCP_ATTACHMENT_ID && $size === 'full';
        $product_render_width = is_array($size) ? (int) ($size[0] ?? 0) : 0;
        $is_product_lcp = self::is_product_target()
            && $attachment_id === self::PRODUCT_LCP_ATTACHMENT_ID
            && ($size === 'woocommerce_single' || $size === 'full' || $product_render_width >= 300);
        if (!$is_calculator_lcp && !$is_article_lcp && !$is_product_lcp) {
            return $attr;
        }

        // Keep only the verified large LCP render discoverable and immediately fetchable.
        $attr['data-no-lazy'] = '1';
        $attr['loading'] = 'eager';
        $attr['fetchpriority'] = 'high';
        $attr['decoding'] = 'async';
        $class_name = $is_product_lcp ? 'k20-product-lcp' : ($is_article_lcp ? 'k20-article-lcp' : 'k20-calculator-lcp');
        $classes = preg_split('/\s+/', trim((string) ($attr['class'] ?? ''))) ?: [];
        if (!in_array($class_name, $classes, true)) {
            $classes[] = $class_name;
        }
        $attr['class'] = trim(implode(' ', array_filter($classes)));
        return $attr;
    }

    public static function lcp_srcset($sources, $size_array, $image_src, $image_meta, $attachment_id) {
        if (!is_array($sources)) {
            return $sources;
        }

        if (self::is_calculator_target() && (int) $attachment_id === self::LCP_ATTACHMENT_ID) {
            $candidate = wp_get_attachment_image_src(self::LCP_672_ATTACHMENT_ID, 'full');
            if (is_array($candidate) && !empty($candidate[0]) && (int) ($candidate[1] ?? 0) === 672) {
                $sources[672] = [
                    'url' => esc_url_raw((string) $candidate[0]),
                    'descriptor' => 'w',
                    'value' => 672,
                ];
            }

            $candidate_768 = wp_get_attachment_image_src(self::LCP_768_ATTACHMENT_ID, 'full');
            if (is_array($candidate_768) && !empty($candidate_768[0]) && (int) ($candidate_768[1] ?? 0) === 768) {
                $sources[768] = [
                    'url' => esc_url_raw((string) $candidate_768[0]),
                    'descriptor' => 'w',
                    'value' => 768,
                ];
            }

            ksort($sources, SORT_NUMERIC);
            return $sources;
        }

        if (self::is_article_target() && (int) $attachment_id === self::ARTICLE_LCP_ATTACHMENT_ID && (int) ($size_array[0] ?? 0) >= 768) {
            $candidate_672 = wp_get_attachment_image_src(self::ARTICLE_LCP_672_ATTACHMENT_ID, 'full');
            if (is_array($candidate_672) && !empty($candidate_672[0]) && (int) ($candidate_672[1] ?? 0) === 672) {
                $sources[672] = [
                    'url' => esc_url_raw((string) $candidate_672[0]),
                    'descriptor' => 'w',
                    'value' => 672,
                ];
            }

            $candidate_768 = wp_get_attachment_image_src(self::ARTICLE_LCP_768_ATTACHMENT_ID, 'full');
            if (is_array($candidate_768) && !empty($candidate_768[0]) && (int) ($candidate_768[1] ?? 0) === 768) {
                // Replace only this article's optimized responsive candidates. All other
                // sources and the featured-image binding remain on attachment 146240.
                $sources[768] = [
                    'url' => esc_url_raw((string) $candidate_768[0]),
                    'descriptor' => 'w',
                    'value' => 768,
                ];
            }

            ksort($sources, SORT_NUMERIC);
        }

        return $sources;
    }
    public static function lcp_sizes($sizes, $size, $image_src, $image_meta, $attachment_id) {
        $requested_width = is_array($size) ? (int) ($size[0] ?? 0) : 0;

        if (self::is_calculator_target() && (int) $attachment_id === self::LCP_ATTACHMENT_ID) {
            // Actual mobile content width is viewport minus the 20px gutters on each side.
            return '(max-width: 767px) calc(100vw - 40px), (max-width: 1200px) 100vw, 1200px';
        }

        if (self::is_article_target()
            && (int) $attachment_id === self::ARTICLE_LCP_ATTACHMENT_ID
            && $requested_width >= 768) {
            // Scope the accurate mobile width only to the article hero render, not the
            // 64px recent-post thumbnail that reuses the same featured attachment.
            return '(max-width: 767px) calc(100vw - 40px), (max-width: 1200px) 100vw, 1200px';
        }

        if (self::is_product_target()
            && (int) $attachment_id === self::PRODUCT_LCP_ATTACHMENT_ID
            && ($requested_width >= 300 || $size === 'woocommerce_single')) {
            return '(max-width: 767px) calc(100vw - 40px), 600px';
        }

        return $sizes;
    }

    public static function script_priority(string $tag, string $handle, string $src): string {
        $target = self::is_calculator_target() || self::is_product_target();
        if (!$target || $handle !== 'google-tag-manager') {
            return $tag;
        }

        if (stripos($tag, 'fetchpriority=') === false) {
            $tag = preg_replace('/<script\b/i', '<script fetchpriority="low"', $tag, 1) ?: $tag;
        }
        return $tag;
    }

    public static function final_html_repairs(string $html): string {
        if ($html === '') return $html;

        if (self::is_article_target()) {
            // LiteSpeed rewrites script tags after WordPress enqueue strategies. Apply this
            // after its optimization pass, only to the two bundles verified as overwhelmingly
            // unused on this article.
            foreach (['elementor-pro-frontend-js', 'pro-elements-handlers-js'] as $id) {
                $pattern = '/<script\\b(?=[^>]*\\bid="' . preg_quote($id, '/') . '")[^>]*>/i';
                $html = preg_replace_callback($pattern, static function (array $match): string {
                    $tag = $match[0];
                    if (preg_match('/\\s(?:async|defer)(?:\\s|=|>)/i', $tag)) return $tag;
                    return preg_replace('/<script\\b/i', '<script defer', $tag, 1) ?: $tag;
                }, $html, 1) ?: $html;
            }

            $html = str_replace(
                'https://keshavarz20.com/wp-content/uploads/2024/06/hossini.jpg',
                'https://keshavarz20.com/wp-content/uploads/2024/06/hossini-150x150.jpg',
                $html
            );
            return $html;
        }

        if (!self::is_product_target()) return $html;

        // Tiny WhatsApp avatar: use the existing 150px derivative instead of 138 KiB full image.
        $html = str_replace(
            'https://keshavarz20.com/wp-content/uploads/2024/06/hossini.jpg',
            'https://keshavarz20.com/wp-content/uploads/2024/06/hossini-150x150.jpg',
            $html
        );

        // The current mobile logo attachment is only 50x50. Use the existing official
        // 100x100 derivative for a 50 CSS-pixel render so DPR=2 devices are not upscaled.
        $html = str_replace(
            'https://keshavarz20.com/wp-content/uploads/2024/05/لوگو-2-کشاورز20-.png',
            self::PRODUCT_MOBILE_LOGO_100_URL,
            $html
        );

        // Restore user zoom while preserving the theme's viewport width/initial scale.
        $html = preg_replace_callback(
            '/<meta\\b(?=[^>]*\\bname=["\\']viewport["\\'])[^>]*>/i',
            static function (array $match): string {
                $tag = preg_replace('/,?\\s*maximum-scale\\s*=\\s*1(?:\\.0)?/i', '', $match[0]) ?: $match[0];
                $tag = preg_replace('/,?\\s*user-scalable\\s*=\\s*(?:no|0)/i', '', $tag) ?: $tag;
                return preg_replace('/\\s+,/', ',', $tag) ?: $tag;
            },
            $html,
            1
        ) ?: $html;

        // Give the account icon a stable accessible name without changing navigation.
        $html = str_replace(
            '<a href="https://keshavarz20.com/my-account" class="login-register">',
            '<a href="https://keshavarz20.com/my-account" class="login-register" aria-label="ورود یا حساب کاربری">',
            $html
        );

        // Owl Carousel renders empty dot buttons. Label only those buttons on this product.
        $dot_index = 0;
        $html = preg_replace_callback(
            '/<button\\b([^>]*\\bclass="[^"]*\\bowl-dot\\b[^"]*"[^>]*)>/i',
            static function (array $match) use (&$dot_index): string {
                $tag = $match[0];
                if (stripos($tag, 'aria-label=') !== false) return $tag;
                $dot_index++;
                return substr($tag, 0, -1) . ' aria-label="اسلاید ' . $dot_index . '">';
            },
            $html
        ) ?: $html;

        // Page-scoped fixes for audited contrast, touch target and warranty aspect ratio.
        $css = '<style id="k20-product-134980-canary-css">'
            . 'body.single-product .woocommerce-breadcrumb,'
            . 'body.single-product .product-rating .average span,'
            . 'body.single-product .woocommerce-review-link,'
            . 'body.single-product .product_meta,body.single-product .product_meta a,'
            . 'body.single-product .woocommerce-product-details__short-description,'
            . 'body.single-product .woocommerce-product-details__short-description p,'
            . 'body.single-product .delivery-text,'
            . 'body.single-product .reviews-columns .button,'
            . 'body.single-product .woocommerce-review__published-date{color:#374151!important;}'
            . 'body.single-product .widget-content .owl-dots .owl-dot{min-width:32px!important;min-height:32px!important;margin:4px!important;padding:0!important;}'
            . 'body.single-product .warranty-message img{width:auto!important;height:32px!important;max-width:32px!important;object-fit:contain!important;}'
            . '</style>';
        $html = str_ireplace('</head>', $css . '</head>', $html);

        return $html;
    }

    public static function dequeue_irrelevant_assets(): void {
        if (self::is_calculator_target()) {
            // Front-end payment gateway help-link CSS is not used by the calculator.
            wp_dequeue_style('help_style');

            // Verified unused on the calculator page.
            wp_dequeue_style('mega-theme-icon');
            return;
        }

        if (self::is_article_target()) {
            // Lighthouse coverage reports this Elementor Pro MegaTheme icon font
            // stylesheet as 100% unused on article 146227. Keep IranKala,
            // WooCommerce, Digits and WhatsApp styles intact.
            wp_dequeue_style('mega-theme-icon');
        }
    }
}

K20_Bridge_V33_Performance::boot();
