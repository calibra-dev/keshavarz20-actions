<?php
// Disposable Docker fixture: WooCommerce order state + Calibra bootstrapping.
if (!class_exists('WooCommerce') || !function_exists('wc_create_order')) {
    throw new RuntimeException('WOOCOMMERCE_NOT_ACTIVE');
}
if (!defined('K20D_VERSION') || K20D_VERSION !== '1.8.17') {
    throw new RuntimeException('CALIBRA_VERSION_RUNTIME_MISMATCH');
}
if (!class_exists('K20_Dashboard_Data')) {
    throw new RuntimeException('CALIBRA_DATA_CLASS_MISSING');
}
$container = wc_get_container();
$controller = $container->get(\Automattic\WooCommerce\Internal\DataStores\Orders\CustomOrdersTableController::class);
$is_hpos = (bool) $controller->custom_orders_table_usage_is_enabled();
$expect_hpos = getenv('CALIBRA_QA_MODE') === 'hpos';
if ($is_hpos !== $expect_hpos) {
    throw new RuntimeException('STORAGE_MODE_MISMATCH');
}
$id = (int) get_option('calibra_qa_order_id', 0);
if (!$id) {
    $order = wc_create_order();
    $order->set_billing_country('IR');
    $order->set_billing_state('THR');
    $order->set_billing_city('تهران');
    $order->set_currency('IRR');
    $order->set_total(137000);
    $order->set_status('completed');
    $order->save();
    if (!(int) $order->get_id()) throw new RuntimeException('TEST_ORDER_CREATE_FAILED');
    update_option('calibra_qa_order_id', (int) $order->get_id());
    echo 'ISOLATED_TEST_ORDER_CREATED' . PHP_EOL;
} else {
    $order = wc_get_order($id);
    if (!$order || $order->get_status() !== 'completed' ||
        (float) $order->get_total() !== 137000.0 ||
        $order->get_billing_city() !== 'تهران') {
        throw new RuntimeException('TEST_ORDER_DATA_NOT_PRESERVED');
    }
    echo 'ISOLATED_TEST_ORDER_SURVIVED_UPGRADE' . PHP_EOL;
}
echo 'CALIBRA_BOOT_OK version=' . K20D_VERSION .
    ' mode=' . ($is_hpos ? 'hpos' : 'legacy') . PHP_EOL;
