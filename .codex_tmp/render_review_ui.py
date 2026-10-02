import os
from pathlib import Path

os.environ['DJANGO_SETTINGS_MODULE'] = 'qlhd.settings'
os.environ['DB_ENGINE'] = 'sqlite'
os.environ['DEBUG'] = 'True'

import django
django.setup()
from django.test.runner import DiscoverRunner
from django.test.utils import setup_test_environment, teardown_test_environment
from django.urls import reverse
from quanly.test_review_workflows import ReviewWorkflowTests
from quanly.models import DotThanhToan

setup_test_environment()
runner = DiscoverRunner(verbosity=0, interactive=False)
old_config = runner.setup_databases()
case = ReviewWorkflowTests('test_duplicate_payment_round_returns_form_error')
case._pre_setup()
try:
    case.setUp()
    dot = DotThanhToan.objects.create(hop_dong=case.contract, nam=2026, thang=9)
    output = Path('.codex_tmp/review_ui')
    output.mkdir(exist_ok=True)
    pages = {
        'payment-error.html': case.client.post(reverse('tao_dot_thanh_toan', args=[case.contract.pk]), case._dot_payload()),
        'detail-error.html': case.client.post(reverse('them_chi_tiet_thanh_toan', args=[dot.pk]), case._detail_payload(so_buoi_thanh_toan=2)),
        'child-date.html': case.client.get(reverse('sua_tre', args=[case.child.pk])),
        'allocation-preview.html': case._allocation_preview(SoTrePHCN=-1),
    }
    extension = case._extension()
    pages['extension-edit.html'] = case.client.get(reverse('sua_gia_han_hop_dong', args=[extension.pk]))
    for name, response in pages.items():
        assert response.status_code == 200, (name, response.status_code)
        (output / name).write_bytes(response.content)
    print('Rendered 5 fixture pages with HTTP 200; isolated test database.')
finally:
    case._post_teardown()
    runner.teardown_databases(old_config)
    teardown_test_environment()
