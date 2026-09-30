<?php
if (!defined('ABSPATH')) exit;

/**
 * Fail-closed recommendation guard for SEO God2 Phase 6 Tier A products.
 *
 * WooCommerce native related products are taxonomy-driven and can surface
 * same-category items without a verified technical compatibility edge.
 * Phase 6 therefore suppresses native related / upsell / cross-sell output
 * for the audited Tier A set until recommendations are promoted from the
 * verified compatibility graph.
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
        add_action('wp_footer', [__CLASS__, 'render_guard_marker'], 999);
    }

    private static function is_guarded_product_id(int $product_id): bool {
        return in_array($product_id, self::TIER_A_PRODUCT_IDS, true);
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

    public static function render_guard_marker(): void {
        if (is_admin() || !function_exists('is_product') || !is_product()) {
            return;
        }
        $product_id = (int) get_queried_object_id();
        if (!self::is_guarded_product_id($product_id)) {
            return;
        }
        echo "\n<!-- k20-phase6-related-guard-" . esc_html((string) $product_id) . " -->\n";
    }
}

K20_Bridge_V33_Recommendation_Guard::boot();
