# K20 Factor 1.0.5 — post-install acceptance

Exact artifact SHA256:
713f5a1e4cb30bd40499fe57c76c1c0323333239d77557382a89d281436a2808

Required gates after install:
- Plugin list, bootstrap and diagnostics all report 1.0.5.
- No PHP fatal or JavaScript console error on K20 Factor admin screens.
- 360/375/390/412 mobile: no page-level horizontal overflow.
- 768/820/1024 tablet: off-canvas opens/closes with backdrop, Escape and click-outside.
- FA sidebar enters from right; EN sidebar enters from left.
- Keyboard focus enters/traps/restores correctly.
- Editor and detail line items render as responsive cards on tablet/mobile.
- Public checkout item list renders as responsive cards at <=820px.
- Product/customer searches operate independently and stay within viewport.
- Editor save controls never cover dropdowns/content.
- Save-only creates/updates one order and generates no PDF.
- Empty delivery-channel selection is rejected client and server side.
- Repeated rapid Save/Send does not duplicate the order/notification.
- Link-only makes no PDF; PDF modes make a valid revision-bound PDF.
- PWSMS test is counted successful only on real provider acceptance.
- Public payment + supported gateway callback updates the same order.
- Paid/expired documents cannot resend a payment link.
- Expire/renew invalidates old token; PDF QR is regenerated when required.
- Stock recheck/gateway grace pass on a controlled stock-managed product.
- HPOS lifecycle passes on HPOS-enabled staging before commercial HPOS claim.
- WooCommerce QIT / activation / security / API compatibility checks pass where available.
