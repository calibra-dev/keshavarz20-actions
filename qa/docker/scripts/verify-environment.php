<?php
// This executes ONLY in an isolated QA WordPress database.
// No customer/account information is read from any live site.
if (!class_exists('WooCommerce') || !function_exists('wc_create_order')) {
    throw new RuntimeException('QA_WOOCOMMERCE_NOT_BOOTED');
}
$storage = getenv('QA_STORAGE_MODE') ?: 'legacy';
$controller = wc_get_container()->get(
    \Automattic\WooCommerce\Internal\DataStores\Orders\CustomOrdersTableController::class
);
$is_hpos = (bool) $controller->custom_orders_table_usage_is_enabled();
if ($is_hpos !== ($storage === 'hpos')) {
    throw new RuntimeException('QA_STORAGE_MODE_MISMATCH');
}
$id = (int) get_option('qa_lab_order_id', 0);
if ($id === 0) {
    $order = wc_create_order();
    $order->set_billing_country('IR');
    $order->set_billing_state('THR');
    $order->set_billing_city('تهران');
    $order->set_currency('IRR');
    $order->set_total(123456);
    $order->set_status('processing');
    $order->save();
    $id = (int) $order->get_id();
    if (!$id) {
        throw new RuntimeException('QA_ORDER_CREATE_FAILED');
    }
    update_option('qa_lab_order_id', $id);
    echo 'QA_ORDER_CREATED' . PHP_EOL;
} else {
    $order = wc_get_order($id);
    if (!$order ||
        $order->get_billing_city() !== 'تهران' ||
        $order->get_currency() !== 'IRR' ||
        (float) $order->get_total() !== 123456.0 ||
        $order->get_status() !== 'processing') {
        throw new RuntimeException('QA_ORDER_DATA_LOST_ON_UPGRADE');
    }
    echo 'QA_ORDER_PRESERVED' . PHP_EOL;
}
echo 'QA_WOOCOMMERCE_RUNTIME_OK mode=' . $storage . PHP_EOL;
