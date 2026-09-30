<?php
if (!defined('ABSPATH')) exit;

/**
 * Fail-closed recommendation guard for SEO God2 Phase 6 Tier A products.
 *
 * Native WooCommerce related products and the active theme's custom related
 * slider can surface same-category products without a verified technical
 * compatibility edge. Tier A therefore exposes no automatic related, upsell,
 * or cross-sell product cards until an edge is explicitly verified.
 */
final class K20_Bridge_V33_Recommendation_Guard {
    private const TIER_A_PRODUCT_IDS = [
        140856, 140718, 135339, 135349, 140853,
        140406, 140760, 140816, 140407, 135337,
        135353, 140454, 135381, 135361, 140674,
        135235, 140014, 135309, 135359, 135667,
    ];

    public static function boot(): void {
        add_filter('woocommerce_related_products', [__CLASS__, 'filter_related_products'], 999, 3);
        add_filter('woocommerce_product_get_upsell_ids', [__CLASS__, 'filter_product_link_ids'], 999, 2);
        add_filter('woocommerce_product_get_cross_sell_ids', [__CLASS__, 'filter_product_link_ids'], 999, 2);
        add_filter('body_class', [__CLASS__, 'guard_body_class'], 999, 1);

        // IranKala renders a separate taxonomy-based related slider that does
        // not consume WooCommerce's related_ids. Remove that exact widget from
        // the final LiteSpeed buffer for guarded products only.
        add_filter('litespeed_buffer_after', [__CLASS__, 'strip_theme_related_widget'], 30, 1);

        add_action('wp_footer', [__CLASS__, 'render_guard_marker'], 999);
    }

    private static function is_guarded_product_id(int $product_id): bool {
        return in_array($product_id, self::TIER_A_PRODUCT_IDS, true);
    }

    private static function current_product_id(): int {
        if (is_admin() || !function_exists('is_product') || !is_product()) {
            return 0;
        }
        return (int) get_queried_object_id();
    }

    public static function filter_related_products($related_product_ids, $product_id, $args) {
        if (self::is_guarded_product_id((int) $product_id)) {
            return [];
        }
        return $related_product_ids;
    }

    public static function filter_product_link_ids($ids, $product) {
        $product_id = is_object($product) && method_exists($product, 'get_id')
            ? (int) $product->get_id()
            : 0;
        if (self::is_guarded_product_id($product_id)) {
            return [];
        }
        return $ids;
    }

    public static function guard_body_class($classes): array {
        $classes = is_array($classes) ? $classes : [];
        $product_id = self::current_product_id();
        if ($product_id && self::is_guarded_product_id($product_id)) {
            $classes[] = 'k20-phase6-related-guard';
            $classes[] = 'k20-phase6-related-guard-' . $product_id;
        }
        return array_values(array_unique($classes));
    }

    public static function strip_theme_related_widget($html) {
        if (!is_string($html) || $html === '' || stripos($html, 'widget-related-products') === false) {
            return $html;
        }

        $product_id = self::current_product_id();
        if (!$product_id || !self::is_guarded_product_id($product_id)) {
            return $html;
        }

        return self::remove_div_by_class($html, 'widget-related-products');
    }

    private static function remove_div_by_class(string $html, string $class_name): string {
        $quoted = preg_quote($class_name, '/');
        $pattern = '/<div\b[^>]*class=(["\'])[^"\']*\b' . $quoted . '\b[^"\']*\1[^>]*>/i';

        // One related widget is expected. A small loop safely handles duplicate
        // theme output without touching unrelated product sliders.
        for ($attempt = 0; $attempt < 4; $attempt++) {
            if (!preg_match($pattern, $html, $opening, PREG_OFFSET_CAPTURE)) {
                break;
            }

            $start = (int) $opening[0][1];
            if (!preg_match_all('/<div\b[^>]*>|<\/div\s*>/i', $html, $tokens, PREG_OFFSET_CAPTURE, $start)) {
                break;
            }

            $depth = 0;
            $end = null;
            foreach ($tokens[0] as $token) {
                $tag = (string) $token[0];
                $offset = (int) $token[1];
                if (stripos($tag, '</div') === 0) {
                    $depth--;
                } else {
                    $depth++;
                }

                if ($depth === 0) {
                    $end = $offset + strlen($tag);
                    break;
                }
            }

            if ($end === null || $end <= $start) {
                break;
            }

            $html = substr($html, 0, $start) . substr($html, $end);
        }

        return $html;
    }

    public static function render_guard_marker(): void {
        $product_id = self::current_product_id();
        if (!$product_id || !self::is_guarded_product_id($product_id)) {
            return;
        }
        echo "\n<!-- k20-phase6-related-guard-" . esc_html((string) $product_id) . " -->\n";
    }
}

K20_Bridge_V33_Recommendation_Guard::boot();
