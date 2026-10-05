# K20 Factor 1.0.4 post-install acceptance

Use exact ZIP SHA256:
c654470876051b2ee94f653cdc1490e5d6360947dbb9f0f7caad6e7588d5f182

Required gates:
- Activate with no PHP fatal/notice.
- Create page never requests /documents/0.
- Product/customer searches operate independently.
- Quantity/price/discount/tax/shipping changes do not reset editor focus.
- Save-only creates/updates pending order without PDF generation.
- Link-only does not generate PDF; PDF modes generate one valid PDF.
- Sending with zero selected channels is blocked and never silently sends SMS.
- Repeated fast clicks do not duplicate an order or notification.
- Provider/PDF failure leaves editor on the same saved document for safe retry.
- URL list filters and pagination work across >7 pages.
- Paid/expired/cancelled documents cannot resend a payment link.
- Clipboard fallback works.
- Editor totals exactly match WooCommerce after reload.
- PWSMS staging message records success only on provider acceptance.
- WhatsApp is automatic only with a real Meta/Webhook/adapter provider.
- Public payment link, billing requirements and WooCommerce order-pay work logged out.
- PDF Persian text/totals/QR are correct.
- Expiry/renew invalidates old link.
- Desktop/mobile + light/dark + WordPress notices have no overlap/overflow/unreadable state.
