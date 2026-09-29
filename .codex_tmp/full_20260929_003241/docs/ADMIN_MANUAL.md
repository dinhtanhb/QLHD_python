# Huong dan quan tri QLHD VietHealth

## 1. Ma tran quyen

| Vai tro | Xem dashboard/bao cao | Danh muc va nghiep vu | Thanh toan | Quan tri du lieu khoa |
|---|---|---|---|---|
| Admin | Co | Toan quyen trong pham vi ung dung | Tao, huy, xac nhan chi | Sua/xoa/mo khoa de phuc vu UAT, co kiem tra an toan |
| Dieu phoi | Co | Phan bo, phan cong, hop dong theo guard | Xem ho so | Khong vuot guard tai chinh |
| Ke toan | Co | Xem nghiep vu can thiet | Tao, huy, xac nhan chi | Khong sua du lieu nghiep vu ngoai pham vi |
| CBDA | Co | Theo pham vi duoc cap | Xem/xuat ho so | Khong sua so lieu goc |

## 2. Migration va database

Truoc khi migrate, tao backup database va chay tren clone:

```powershell
$env:DEBUG = 'True'
python manage.py check
python manage.py migrate
python manage.py makemigrations --check --dry-run
```

Migration `0033` tao cau hinh thue, so phieu thanh toan va chi tiet phieu. Khong chay migration truc tiep tren database that neu chua co backup va ke hoach rollback.

## 3. Kiem tra du lieu

Chay cac lenh chi doc truoc khi chuyen so cu:

```powershell
python manage.py bao_cao_nhat_ky_thieu_hop_dong
python manage.py bao_cao_so_thanh_toan
python manage.py chuyen_so_thanh_toan_cu --help
```

Lenh chuyen so mac dinh dry-run; chi dung `--force` sau khi da doi chieu va phe duyet.

## 4. Backup va ban giao

Backup review chi gom file can review; backup full gom ma nguon, migration, template va tai lieu. Khong dua `.env`, database, du lieu that, `venv`, log, file tam hoac thu muc backups vao ZIP.

Sau moi dot thay doi, ghi vao `docs/PROJECT_PROGRESS.md`: file da sua, test, ket qua dinh luong, rui ro va buoc tiep theo. Chi commit/push khi da kiem tra diff va co yeu cau/uy quyen ro rang.

## 5. Xu ly sai lech thanh toan

Neu nhat ky khac phieu, kiem tra `ChiTietPhieuThanhToan` dang hoat dong. Snapshot phieu la nguon xuat ho so; nhat ky da thanh toan duoc bao ve khoi sua cac truong anh huong tien. Khong xoa cung du lieu de sua nhanh; tao dieu chinh va ghi ly do.
