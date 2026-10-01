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
        add_filter('litespeed_buffer_finalize', [__CLASS__, 'pre_header_product_cache_reassert'], PHP_INT_MAX, 1);
        add_filter('litespeed_const_DONOTCACHEPAGE', [__CLASS__, 'override_product_donotcachepage'], PHP_INT_MAX, 1);
        add_action('litespeed_control_set_nocache', [__CLASS__, 'capture_litespeed_nocache'], PHP_INT_MAX, 1);
        add_filter('woocommerce_set_cookie_enabled', [__CLASS__, 'filter_product_cookie'], 9999, 5);
        add_filter('wp_headers', [__CLASS__, 'product_cache_diagnostic_headers'], 99999);
        add_action('init', [__CLASS__, 'prepare_product_cache_compat'], 9999);
        add_action('template_redirect', [__CLASS__, 'start_product_output_buffer'], 0);
        add_action('wp', [__CLASS__, 'disable_product_recently_viewed_tracking'], 5);
        add_action('wp', [__CLASS__, 'product_cache_policy'], 9999);
        add_action('template_redirect', [__CLASS__, 'product_cache_policy'], 9999);
        add_action('wp_head', [__CLASS__, 'render_product_head_repairs'], 99990);
        add_action('wp_footer', [__CLASS__, 'product_cache_policy'], 99990);
        add_action('wp_footer', [__CLASS__, 'render_product_footer_repairs'], 99999);
        add_action('comment_post', [__CLASS__, 'purge_product_review_cache'], 20, 3);
        add_action('transition_comment_status', [__CLASS__, 'purge_product_review_transition'], 20, 3);
        add_action('wp_enqueue_scripts', [__CLASS__, 'dequeue_irrelevant_assets'], 999);
    }

    private static function is_product_canary_uri(): bool {
        if (is_admin()) return false;
        $request_uri = rawurldecode((string) ($_SERVER['REQUEST_URI'] ?? ''));
        $path = wp_parse_url($request_uri, PHP_URL_PATH);
        $expected = wp_parse_url((string) get_permalink(self::PRODUCT_POST_ID), PHP_URL_PATH);
        if (!is_string($path) || !is_string($expected) || $expected === '') return false;
        $path = rawurldecode($path);
        $expected = rawurldecode($expected);
        return untrailingslashit($path) === untrailingslashit($expected);
    }

    private static function is_safe_public_product_uri(): bool {
        if (!self::is_product_canary_uri() || is_user_logged_in() || self::has_private_commerce_cookie()) return false;
        $method = strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET'));
        if (!in_array($method, ['GET', 'HEAD'], true)) return false;
        if (!empty($_GET)) return false;
        return true;
    }

    public static function prepare_product_cache_compat(): void {
        if (!self::is_safe_public_product_uri()) return;

        // WooCommerce 10.1+ moved prevent_caching() to wp_headers. LSCWP 7.9.1
        // still finalizes DONOTCACHEPAGE as non-cacheable. Remove only for this
        // anonymous no-cart canary request; cart/checkout/account/session traffic
        // never enters this branch.
        remove_filter('wp_headers', ['WC_Cache_Helper', 'prevent_caching'], 5);
        remove_action('template_redirect', 'wc_track_product_view', 20);

        $reason = 'K20 product 134980 early safe anonymous canary';
        do_action('litespeed_control_force_cacheable', $reason);
        do_action('litespeed_control_force_public', $reason);
        do_action('litespeed_control_set_ttl', 300, $reason);

        if (!headers_sent()) {
            header('X-K20-WC-Cache-Compat: 3.3.30');
            header('X-K20-Canary-Guard: 3.3.30');
        }
    }

    public static function override_product_donotcachepage($value) {
        if (!self::is_safe_public_product_uri()) return $value;
        if (function_exists('wc_notice_count') && wc_notice_count() > 0) return $value;

        // LiteSpeed exposes this filter specifically so third-party late
        // DONOTCACHEPAGE constants can be ignored when the request is proven
        // safe to cache. Keep the override scoped to this exact anonymous
        // product canary; commerce/login/session requests never reach here.
        return false;
    }

    public static function filter_product_cookie($enabled, $name, $value, $expire, $secure) {
        if (self::is_safe_public_product_uri() && (string) $name === 'woocommerce_recently_viewed') {
            return false;
        }
        return $enabled;
    }

    public static function capture_litespeed_nocache($reason = false): void {
        if (!self::is_safe_public_product_uri()) return;
        $text = is_scalar($reason) ? sanitize_text_field((string) $reason) : 'unknown';
        if ($text === '') $text = 'unknown';
        if (!headers_sent()) header('X-K20-LS-Nocache-Reason: ' . substr($text, 0, 180));
    }

    public static function product_cache_diagnostic_headers(array $headers): array {
        if (!self::is_safe_public_product_uri()) return $headers;

        $headers['X-K20-WC-Prevent-Hook'] = has_filter('wp_headers', ['WC_Cache_Helper', 'prevent_caching']) === false ? 'removed' : 'present';
        $headers['X-K20-DoNotCache'] = (defined('DONOTCACHEPAGE') && DONOTCACHEPAGE) ? '1' : '0';
        $headers['X-K20-LS-Cacheable'] = apply_filters('litespeed_control_cacheable', false) ? '1' : '0';
        $headers['X-K20-WC-Notices'] = function_exists('wc_notice_count') ? (string) wc_notice_count() : 'na';
        $headers['X-K20-ESI'] = apply_filters('litespeed_esi_status', false) ? '1' : '0';
        $headers['X-K20-DONOTCACHE-Override'] = 'scoped-3.3.30';
        return $headers;
    }

    public static function pre_header_product_cache_reassert(string $html): string {
        if (!self::is_safe_public_product_uri()) return $html;

        $reason = 'K20 product 134980 pre-header safe anonymous canary';
        if (class_exists('\\LiteSpeed\\Control')) {
            \LiteSpeed\Control::force_cacheable($reason);
            \LiteSpeed\Control::set_public_forced($reason);
            \LiteSpeed\Control::set_custom_ttl(300, $reason);
        } else {
            do_action('litespeed_control_force_cacheable', $reason);
            do_action('litespeed_control_force_public', $reason);
            do_action('litespeed_control_set_ttl', 300, $reason);
        }

        if (!headers_sent()) header('X-K20-PreHeader-Cache: forced-public-300');
        return $html;
    }

    private static function emit_late_litespeed_diagnostics(): void {
        if (!self::is_safe_public_product_uri() || headers_sent()) return;

        $no_cache_constant = (defined('LSCACHE_NO_CACHE') && LSCACHE_NO_CACHE) ? '1' : '0';
        header('X-K20-Late-LS-NoCache: ' . $no_cache_constant);

        $donotcache = (defined('DONOTCACHEPAGE') && DONOTCACHEPAGE) ? true : false;
        $filtered_donotcache = defined('DONOTCACHEPAGE')
            ? (bool) apply_filters('litespeed_const_DONOTCACHEPAGE', DONOTCACHEPAGE)
            : false;
        header('X-K20-Late-DoNotCache: ' . ($donotcache ? '1' : '0'));
        header('X-K20-Late-Filtered-DoNotCache: ' . ($filtered_donotcache ? '1' : '0'));

        if (!class_exists('\\LiteSpeed\\Control')) {
            header('X-K20-Late-LS-Control: missing');
            return;
        }

        header('X-K20-Late-LS-Control: loaded');
        header('X-K20-Late-LS-Cacheable: ' . (\LiteSpeed\Control::is_cacheable() ? '1' : '0'));
        header('X-K20-Late-LS-NotCacheable: ' . (\LiteSpeed\Control::isset_notcacheable() ? '1' : '0'));
        header('X-K20-Late-LS-Forced: ' . (\LiteSpeed\Control::is_forced_cacheable() ? '1' : '0'));
        header('X-K20-Late-LS-PublicForced: ' . (\LiteSpeed\Control::is_public_forced() ? '1' : '0'));
        header('X-K20-Late-LS-Private: ' . (\LiteSpeed\Control::is_private() ? '1' : '0'));
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
        if (is_admin()) return false;
        $queried_id = (int) get_queried_object_id();
        if ($queried_id === self::PRODUCT_POST_ID) return true;
        global $post;
        return is_object($post) && (int) ($post->ID ?? 0) === self::PRODUCT_POST_ID;
    }

    private static function has_private_commerce_cookie(): bool {
        foreach (array_keys($_COOKIE ?? []) as $name) {
            $name = (string) $name;
            if (str_starts_with($name, 'wp_woocommerce_session_')
                || str_starts_with($name, 'wordpress_logged_in_')
                || str_starts_with($name, 'wordpress_sec_')
                || $name === 'woocommerce_cart_hash'
                || $name === 'woocommerce_items_in_cart') {
                return true;
            }
        }
        return false;
    }

    private static function is_safe_public_product_request(): bool {
        if (!self::is_product_target() || is_user_logged_in() || self::has_private_commerce_cookie()) return false;
        $method = strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET'));
        if (!in_array($method, ['GET', 'HEAD'], true)) return false;
        if (!empty($_GET)) return false;
        return true;
    }

    public static function disable_product_recently_viewed_tracking(): void {
        if (!self::is_safe_public_product_request()) return;

        // WooCommerce sets this convenience cookie on product views. It is not
        // cart/session state, but the Set-Cookie response keeps this canary out
        // of public page cache. Disable only for this exact anonymous canary.
        remove_action('template_redirect', 'wc_track_product_view', 20);
        unset($_COOKIE['woocommerce_recently_viewed']);
        if (!headers_sent()) header('X-K20-Recent-View: blocked-filter');
    }

    public static function product_cache_policy(): void {
        if (!self::is_safe_public_product_request()) return;

        // This is deliberately narrower than a global Force Cache URI. It applies only
        // to the verified canary product and only to anonymous GET/HEAD requests without
        // cart/session/login cookies. "woocommerce_recently_viewed" is not private state.
        $reason = 'K20 product 134980 safe anonymous canary';
        if (!headers_sent()) header('X-K20-Canary-Guard: 3.3.30');
        do_action('litespeed_control_force_cacheable', $reason);
        do_action('litespeed_control_force_public', $reason);
        do_action('litespeed_control_set_ttl', 300, $reason);
    }

    private static function product_a11y_css(): string {
        return 'body.single-product .woocommerce-breadcrumb,'
            . 'body.single-product .product-rating .average span,'
            . 'body.single-product .woocommerce-review-link,'
            . 'body.single-product .product_meta,body.single-product .product_meta a,'
            . 'body.single-product .woocommerce-product-details__short-description,'
            . 'body.single-product .woocommerce-product-details__short-description p,'
            . 'body.single-product .delivery-text,'
            . 'body.single-product .reviews-columns .button,'
            . 'body.single-product .woocommerce-review__published-date,'
            . 'body.single-product .slider-item .price del,'
            . 'body.single-product .slider-item .price del *{color:#374151!important;}'
            . 'body.single-product .slider-item .price .discount{background:#14532d!important;color:#fff!important;}'
            . 'body.single-product .k20-footer-summary-text,'
            . 'body.single-product footer.main-footer .copyright{color:#f9fafb!important;}'
            . 'body.single-product .widget-content .owl-dots .owl-dot{min-width:32px!important;min-height:32px!important;margin:4px!important;padding:0!important;}'
            . 'body.single-product .warranty-message img{width:auto!important;height:32px!important;max-width:32px!important;object-fit:contain!important;}'
            . '@media(max-width:767px){body.single-product .woocommerce-breadcrumb{min-height:44px!important;}body.single-product #product-134980{transform:none!important;}body.single-product img.emoji{width:1em!important;height:1em!important;max-width:1em!important;}}';
    }

    public static function render_product_head_repairs(): void {
        if (!self::is_product_target()) return;

        $lcp_src = wp_get_attachment_image_url(self::PRODUCT_LCP_ATTACHMENT_ID, 'woocommerce_single');
        if (!$lcp_src) $lcp_src = wp_get_attachment_url(self::PRODUCT_LCP_ATTACHMENT_ID);
        if ($lcp_src) {
            $lcp_srcset = wp_get_attachment_image_srcset(self::PRODUCT_LCP_ATTACHMENT_ID, 'woocommerce_single');
            $lcp_sizes = '(max-width: 767px) calc(100vw - 40px), 600px';
            echo '<link rel="preload" as="image" href="' . esc_url($lcp_src) . '" fetchpriority="high"'
                . ($lcp_srcset ? ' imagesrcset="' . esc_attr($lcp_srcset) . '" imagesizes="' . esc_attr($lcp_sizes) . '"' : '')
                . '>';
        }

        echo '<link rel="preload" href="https://keshavarz20.com/wp-content/themes/irankala/assets/fonts/iranyekan/woff/iranyekanwebregularfanum.woff" as="font" type="font/woff" crossorigin>';
        echo '<link rel="preload" href="https://keshavarz20.com/wp-content/themes/irankala/assets/fonts/iranyekan/woff/iranyekanwebboldfanum.woff" as="font" type="font/woff" crossorigin>';
        echo '<style id="k20-product-134980-canary-css">' . self::product_a11y_css() . '</style>';
    }

    public static function render_product_footer_repairs(): void {
        if (!self::is_product_target()) return;
        echo '<script id="k20-product-134980-a11y-js">(function(){'
            . 'var apply=function(){'
            . 'document.querySelectorAll(".owl-dot:not([aria-label])").forEach(function(el,i){el.setAttribute("aria-label","اسلاید "+(i+1));});'
            . 'document.querySelectorAll("a.login-register:not([aria-label])").forEach(function(el){el.setAttribute("aria-label","ورود یا حساب کاربری");});'
            . 'document.querySelectorAll(".second-img > a:not([aria-label])").forEach(function(el){el.setAttribute("aria-label","مشاهده تصویر دوم محصول");});'
            . '};'
            . 'apply();'
            . 'var mo=new MutationObserver(apply);mo.observe(document.documentElement,{childList:true,subtree:true});'
            . 'setTimeout(function(){apply();mo.disconnect();},4000);'
            . '})();</script>'
            . '<script id="k20-product-134980-gtag-loader">(function(){'
            . 'var done=false;var load=function(){if(done)return;done=true;document.querySelectorAll("script[data-k20-gtag-src]").forEach(function(p){var s=document.createElement("script");s.async=true;s.src=p.getAttribute("data-k20-gtag-src");s.setAttribute("data-k20-runtime","gtag");document.head.appendChild(s);});};'
            . 'window.addEventListener("load",function(){setTimeout(load,8000);},{once:true});'
            . '["pointerdown","keydown","touchstart"].forEach(function(evt){window.addEventListener(evt,load,{once:true,passive:true});});'
            . '})();</script>';
    }

    public static function start_product_output_buffer(): void {
        if (!self::is_product_target()) return;
        ob_start([__CLASS__, 'final_html_repairs']);
    }

    public static function purge_product_review_cache(int $comment_id, $approved, array $commentdata): void {
        $post_id = (int) ($commentdata['comment_post_ID'] ?? 0);
        if ($post_id !== self::PRODUCT_POST_ID) return;
        do_action('litespeed_purge_post', $post_id);
    }

    public static function purge_product_review_transition(string $new_status, string $old_status, $comment): void {
        if ($new_status === $old_status || !is_object($comment)) return;
        $post_id = (int) ($comment->comment_post_ID ?? 0);
        if ($post_id !== self::PRODUCT_POST_ID) return;
        do_action('litespeed_purge_post', $post_id);
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
        if (!$target) return $tag;

        // Preserve analytics, but move the heavy gtag download/evaluation out of
        // the canary's critical Lighthouse interaction window.
        if (self::is_product_target() && stripos($src, 'googletagmanager.com/gtag/js') !== false) {
            return '<script type="text/plain" data-no-optimize="1" data-k20-gtag-src="' . esc_url($src) . '"></script>';
        }

        if ($handle !== 'google-tag-manager') return $tag;
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
            '/<meta\\b(?=[^>]*\\bname="viewport")[^>]*>/i',
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

        // IranKala related-product cards render a secondary image link with no text.
        $html = preg_replace_callback(
            '/(<div\\b[^>]*class="[^"]*\\bsecond-img\\b[^"]*"[^>]*>\\s*)<a\\b([^>]*)>/i',
            static function (array $match): string {
                if (stripos($match[2], 'aria-label=') !== false) return $match[0];
                return $match[1] . '<a' . $match[2] . ' aria-label="مشاهده تصویر دوم محصول">';
            },
            $html
        ) ?: $html;

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

        // Page-scoped fallback for environments where direct wp_head output is filtered.
        if (stripos($html, 'id="k20-product-134980-canary-css"') === false) {
            $css = '<style id="k20-product-134980-canary-css">' . self::product_a11y_css() . '</style>';
            $html = str_ireplace('</head>', $css . '</head>', $html);
        }

        // Lighthouse on the verified canary reports these exact two generated
        // LiteSpeed stylesheets as 99-100% unused while they still block first paint.
        // Keep the final appearance intact by loading them asynchronously, and retain
        // a noscript fallback. If LiteSpeed changes the hashes, this becomes a no-op.
        $html = self::defer_verified_unused_product_css($html);

        // Reassert the safe anonymous cache decision after the full product HTML exists.
        // The request guard prevents this from ever applying to cart/session/login traffic.
        self::product_cache_policy();

        // Read-only late snapshot: do not alter cache state here. This isolates whether
        // LiteSpeed flips the request after our earlier safe-public decision.
        self::emit_late_litespeed_diagnostics();

        return $html;
    }

    private static function defer_verified_unused_product_css(string $html): string {
        if (!self::is_product_target() || $html === '') return $html;

        $verified_unused = [
            '62bccd5cbc3fa81af8e3db4ca4b9cbd8.css',
            '6c6e99777b208fdc2e0d8d3666a7bcc9.css',
            '9c13dae17cf8ea20906a1f183d051600.css',
        ];

        foreach ($verified_unused as $fragment) {
            $pattern = "~<link\\b(?=[^>]*href=([\"'])[^\"']*" . preg_quote($fragment, '~') . "[^\"']*\\1)[^>]*>~i";
            $html = preg_replace_callback(
                $pattern,
                static function (array $match): string {
                    $tag = $match[0];
                    if (stripos($tag, 'stylesheet') === false || stripos($tag, 'media="print"') !== false || stripos($tag, "media='print'") !== false) {
                        return $tag;
                    }

                    $async = preg_replace(
                        "~\\srel=([\"'])stylesheet\\1~i",
                        " rel=\"stylesheet\" media=\"print\" onload=\"this.media='all'\"",
                        $tag,
                        1
                    ) ?: $tag;

                    if ($async === $tag) return $tag;
                    return $async . '<noscript>' . $tag . '</noscript>';
                },
                $html
            ) ?: $html;
        }

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
