#!/usr/bin/env python3
from pathlib import Path
import re

p=Path("growthos-membership/k20-membership-value-v1.snippet.php.txt")
s=p.read_text(encoding="utf-8")

required=[
    "project_saved","calculation_saved","registration_completed",
    "technical_question_submitted","proforma_requested",
    "woocommerce_account_dashboard","register_rest_route",
    "_k20_member_value_v1","wp_verify_nonce","is_user_logged_in"
]
for token in required:
    assert token in s, token

forbidden=[
    r"set_sale_price\s*\(", r"set_price\s*\(", r"set_regular_price\s*\(",
    r"\$wpdb\b", r"wp_create_user\s*\(", r"wp_update_user\s*\(",
    r"add_role\s*\(", r"remove_role\s*\(", r"eval\s*\(",
    r"shell_exec\s*\(", r"exec\s*\(", r"file_put_contents\s*\("
]
for pat in forbidden:
    assert not re.search(pat,s,re.I), pat

assert "price" not in re.sub(r"اطلاعات قیمت", "", s).lower()
print("PASS membership snippet static guard")

assert '<?php' not in s and '?>' not in s, 'php_tags'
