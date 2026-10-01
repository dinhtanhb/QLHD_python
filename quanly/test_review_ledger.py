from datetime import date, time
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext

from .management.commands.chuyen_so_thanh_toan_cu import Command
from .models import ChiTietThanhToan, DotThanhToan, NhatKyThucHien, PhieuThanhToan
from .services import payment_ledger
from .services.payment_ledger import huy_phieu, tao_phieu_thanh_toan
from .tests import SettlementReportingTestBase


class LegacyLedgerReviewTests(SettlementReportingTestBase):
    def setUp(self):
        super().setUp()
        self.assignment = self._assignment(self.alloc1, self.child1, nhom=self.g1)
        self.contract = self._contract("HD-LEGACY-REVIEW", self.cb1, self.g1)

    def _legacy(self, month=9, ky=1, **dot_values):
        journal = self._journal(self.contract, self.assignment, date(2026, month, 10), ky=ky, buoi=2, di_lai=1)
        dot, _created = DotThanhToan.objects.get_or_create(
            hop_dong=self.contract, nam=2026, thang=month,
            defaults={"ngay_de_nghi": date(2026, month, 20), **dot_values},
        )
        return ChiTietThanhToan.objects.create(
            dot_thanh_toan=dot, nhat_ky=journal, so_buoi_thanh_toan=2, so_luot_di_lai=1,
        )

    def _convert(self, force=False, **options):
        output = StringIO()
        call_command("chuyen_so_thanh_toan_cu", force=force, stdout=output, **options)
        return output.getvalue()

    def test_dry_run_reports_counts_without_writing(self):
        self._legacy()
        output = self._convert()
        self.assertIn("selected 1 details, planned 1 vouchers / 1 details", output)
        self.assertEqual(PhieuThanhToan.objects.count(), 0)

    def test_pending_legacy_request_is_not_marked_paid_and_replay_skips_each_row(self):
        first = self._legacy()
        self._legacy()
        self._convert(force=True)
        voucher = PhieuThanhToan.objects.get()
        self.assertEqual(voucher.trang_thai, "CHO_CHI")
        self.assertIsNone(voucher.ngay_chi)
        self.assertEqual(voucher.ngay_lap, first.dot_thanh_toan.ngay_de_nghi)
        self.assertEqual(voucher.tong_tien_cong + voucher.tong_tien_di_lai, Decimal("900000"))
        self.assertEqual(voucher.chi_tiet.count(), 2)
        self.assertIn("skipped 2 details, conflicted 0 details", self._convert(force=True))
        self.assertEqual(PhieuThanhToan.objects.count(), 1)

    def test_same_period_in_two_legacy_batches_blocks_entire_conversion(self):
        self._legacy(month=9, ky=1)
        self._legacy(month=10, ky=1)
        output = self._convert()
        self.assertIn("planned 0 vouchers", output)
        self.assertIn("conflicted 2 details", output)
        with self.assertRaisesMessage(CommandError, "no data written"):
            self._convert(force=True)
        self.assertEqual(PhieuThanhToan.objects.count(), 0)

    def test_partly_converted_group_does_not_silently_skip_remaining_rows(self):
        self._legacy()
        tao_phieu_thanh_toan(self.cb1, self.contract, 1)
        self._legacy()
        output = self._convert()
        self.assertIn("skipped 0 details, conflicted 2 details", output)
        self.assertIn("partially converted", output)
        with self.assertRaises(CommandError):
            self._convert(force=True)
        self.assertEqual(PhieuThanhToan.objects.get().chi_tiet.count(), 1)

    def test_unknown_status_blocks_write_instead_of_inventing_payment_date(self):
        self._legacy(trang_thai="DA_THANH_TOAN")
        self.assertIn("no verified mapping", self._convert())
        with self.assertRaises(CommandError):
            self._convert(force=True)
        self.assertEqual(PhieuThanhToan.objects.count(), 0)

    def test_changed_historical_rate_is_reported_before_any_write(self):
        detail = self._legacy()
        type(detail.nhat_ky).objects.filter(pk=detail.nhat_ky_id).update(don_gia_cong=Decimal("300000"))
        self.assertIn("stored legacy amount differs", self._convert())
        with self.assertRaises(CommandError):
            self._convert(force=True)
        self.assertEqual(PhieuThanhToan.objects.count(), 0)

    def test_partial_legacy_payment_does_not_consume_unpaid_remainder(self):
        detail = self._legacy()
        for sessions, trips, amount in ((1, 1, "250000"), (2, 0, "400000")):
            with self.subTest(sessions=sessions, trips=trips):
                ChiTietThanhToan.objects.filter(pk=detail.pk).update(
                    so_buoi_thanh_toan=sessions, so_luot_di_lai=trips, thanh_tien=Decimal(amount),
                )
                self.assertIn("covers only part of a journal", self._convert())
                with self.assertRaises(CommandError):
                    self._convert(force=True)
                self.assertEqual(PhieuThanhToan.objects.count(), 0)

    def test_late_integrity_failure_rolls_back_all_created_vouchers(self):
        self._legacy(month=9, ky=1)
        self._legacy(month=10, ky=2)
        original = Command._create_voucher
        calls = []

        def fail_later(command, *args):
            calls.append(args)
            if len(calls) == 2:
                raise IntegrityError("simulated competing voucher")
            return original(command, *args)

        with patch.object(Command, "_create_voucher", fail_later):
            with self.assertRaisesMessage(CommandError, "all writes rolled back"):
                self._convert(force=True)
        self.assertEqual(len(calls), 2)
        self.assertEqual(PhieuThanhToan.objects.count(), 0)

    def test_date_bounds_are_validated_before_querying(self):
        for options in ({"from_date": "bad"}, {"from_date": "2026-10-01", "to_date": "2026-09-01"}):
            with self.subTest(options=options), self.assertRaises(CommandError):
                self._convert(**options)

    def test_cancellation_reads_parent_contract_before_mutating_voucher(self):
        self._legacy()
        voucher = tao_phieu_thanh_toan(self.cb1, self.contract, 1)
        with CaptureQueriesContext(connection) as queries:
            huy_phieu(voucher, "Review cancellation")
        sql = [query["sql"] for query in queries]
        quote = connection.ops.quote_name
        contract_read = next(i for i, query in enumerate(sql) if f"FROM {quote('quanly_hopdong')}" in query)
        voucher_read = next(i for i, query in enumerate(sql) if i > contract_read and f"FROM {quote('quanly_phieuthanhtoan')}" in query)
        mutation = next(i for i, query in enumerate(sql) if query.startswith("UPDATE"))
        self.assertLess(contract_read, voucher_read)
        self.assertLess(voucher_read, mutation)

    def test_voucher_uses_only_the_batchs_prelocked_journals(self):
        first = self._legacy()
        locked_ids = [first.nhat_ky_id]
        later = self._legacy()
        voucher = tao_phieu_thanh_toan(self.cb1, self.contract, 1, locked_journal_ids=locked_ids)
        self.assertEqual(list(voucher.chi_tiet.values_list("nhat_ky_id", flat=True)), locked_ids)
        self.assertFalse(later.nhat_ky.chi_tiet_phieu_thanh_toan.exists())

    def test_rebuild_is_deferred_until_the_enclosing_transaction_commits(self):
        detail = self._legacy()
        row = detail.nhat_ky
        with patch.object(NhatKyThucHien, "recalculate_day") as rebuild:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                row.ghi_chu = "Deferred rebuild"
                row.save()
                rebuild.assert_not_called()
            self.assertEqual(len(callbacks), 1)
            rebuild.assert_called_once_with(row.ngay_thuc_hien)


@skipUnlessDBFeature("has_select_for_update")
class JournalSnapshotConcurrencyTests(TransactionTestCase):
    """Use separate real DB connections; SQLite cannot exercise row locks."""

    setUp = SettlementReportingTestBase.setUp
    _assignment = SettlementReportingTestBase._assignment
    _contract = SettlementReportingTestBase._contract
    _journal = SettlementReportingTestBase._journal

    def _scenario(self):
        assignment = self._assignment(self.alloc1, self.child1, nhom=self.g1)
        contract = self._contract("HD-CONCURRENT-SNAPSHOT", self.cb1, self.g1)
        journal = self._journal(
            contract, assignment, date(2026, 9, 10), buoi=2,
            gio_bat_dau=time(9), gio_ket_thuc=time(10), dia_diem_ct="Khác",
        )
        return contract, journal

    @staticmethod
    def _worker(action):
        close_old_connections()
        try:
            return action()
        finally:
            connection.close()

    def _assert_snapshot(self, journal):
        journal.refresh_from_db()
        detail = journal.chi_tiet_phieu_thanh_toan.get(hoat_dong=True)
        self.assertEqual(detail.so_buoi, journal.so_buoi_thuc_hien)
        self.assertEqual(detail.so_luot_di_lai_cbct, journal.so_luot_di_lai_cbct)
        self.assertEqual(detail.tien_cong + detail.tien_di_lai, journal.thanh_tien)

    def test_snapshot_waits_for_edit_and_reads_committed_money(self):
        contract, journal = self._scenario()
        entered, release, snapshot_started, snapshot_finished = Event(), Event(), Event(), Event()
        original = NhatKyThucHien._save_locked

        def pause_edit(instance, *args, **kwargs):
            if instance.pk == journal.pk:
                entered.set()
                if not release.wait(10):
                    raise AssertionError("edit release timed out")
            return original(instance, *args, **kwargs)

        def edit():
            row = NhatKyThucHien.objects.get(pk=journal.pk)
            row.so_buoi_thuc_hien = 3
            row.save(recalculate_travel=False)

        def create():
            snapshot_started.set()
            voucher = tao_phieu_thanh_toan(self.cb1, contract, 1)
            snapshot_finished.set()
            return voucher.pk

        with patch.object(NhatKyThucHien, "_save_locked", pause_edit), ThreadPoolExecutor(max_workers=2) as pool:
            editing = pool.submit(self._worker, edit)
            try:
                self.assertTrue(entered.wait(10))
                creating = pool.submit(self._worker, create)
                self.assertTrue(snapshot_started.wait(10))
                self.assertFalse(snapshot_finished.wait(0.3))
            finally:
                release.set()
            editing.result(timeout=15)
            creating.result(timeout=15)
        self._assert_snapshot(journal)
        self.assertEqual(journal.so_buoi_thuc_hien, 3)

    def _snapshot_first(self, operation, expected_validation=False):
        contract, journal = self._scenario()
        entered, release, action_started, action_finished = Event(), Event(), Event(), Event()
        original = payment_ledger._eligible_journals

        def pause_snapshot(*args, **kwargs):
            entered.set()
            if not release.wait(10):
                raise AssertionError("snapshot release timed out")
            return original(*args, **kwargs)

        def action():
            action_started.set()
            try:
                operation(journal.pk)
            except ValidationError:
                if not expected_validation:
                    raise
                return "protected"
            finally:
                action_finished.set()
            return "completed"

        with patch.object(payment_ledger, "_eligible_journals", pause_snapshot), ThreadPoolExecutor(max_workers=2) as pool:
            creating = pool.submit(self._worker, lambda: tao_phieu_thanh_toan(self.cb1, contract, 1).pk)
            try:
                self.assertTrue(entered.wait(10))
                working = pool.submit(self._worker, action)
                self.assertTrue(action_started.wait(10))
                self.assertFalse(action_finished.wait(0.3))
            finally:
                release.set()
            creating.result(timeout=15)
            result = working.result(timeout=15)
        self._assert_snapshot(journal)
        self.assertEqual(journal.so_buoi_thuc_hien, 2)
        return result

    def test_edit_waits_for_snapshot_and_rechecks_paid_protection(self):
        def edit(pk):
            row = NhatKyThucHien.objects.get(pk=pk)
            row.so_buoi_thuc_hien = 3
            row.save(recalculate_travel=False)

        self.assertEqual(self._snapshot_first(edit, expected_validation=True), "protected")

    def test_day_rebuild_waits_for_snapshot_and_preserves_paid_money(self):
        self.assertEqual(self._snapshot_first(lambda _pk: NhatKyThucHien.recalculate_day(date(2026, 9, 10))), "completed")
