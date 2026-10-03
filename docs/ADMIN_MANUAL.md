# Huong dan quan tri QLHD VietHealth

**Cập nhật 02/10/2026:** dùng nhánh `main`. Bộ SQLite tại commit nền `5628f468`: 180 đạt, 3 test đồng thời bỏ qua; cần MySQL riêng để chạy ba test này. Checklist tạo/sửa/xóa và đối chiếu phiếu tại [UAT_CURRENT.md](UAT_CURRENT.md). Kiểm thử trong phiên này dùng CSDL SQLite giả lập, chưa truy cập MySQL hoặc Edge trên máy Windows của người dùng.

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

Từ đợt sửa 01/10/2026, lệnh báo riêng số chi tiết được chọn, số phiếu/chi tiết dự kiến chuyển, số chi tiết đã nằm trong phiếu và số xung đột. `--from`/`--to` nhận ngày ISO `YYYY-MM-DD`. Nếu có xung đột, `--force` dừng trước khi ghi; lỗi ghi ở nhóm sau rollback toàn bộ lượt.

Không tự gộp các đợt cũ cùng CBCT/HĐ/kỳ hoặc bỏ cả nhóm khi mới chuyển một phần. Đợt cũ `CHO_THANH_TOAN` được chuyển thành `CHO_CHI`, không gán ngày đã chi từ ngày đề nghị. Trạng thái cũ không có cách khớp được kiểm chứng, nhật ký thiếu/lệch hợp đồng, khối lượng thanh toán một phần hoặc đơn giá lịch sử đã thay đổi được báo để đối chiếu; không tự điều chỉnh tiền hay xóa lịch sử. Chỉ xác nhận đã chi qua quy trình thanh toán khi có chứng từ/ngày thực tế.

`setup_roles` chỉ tạo các nhóm quyền mặc định, không kích hoạt lại hoặc nâng quyền tài khoản tên `admin`. Tài khoản bị thu hồi quyền giữ nguyên trạng thái. Tạo quản trị viên bằng `createsuperuser`; chỉ cấp nhóm `Admin` cho tài khoản đang hoạt động khi có chủ đích. Quyền Admin trong ứng dụng không còn dựa vào tên đăng nhập. Lệnh đồng bộ trạng thái HĐ báo đúng số thay đổi đã lưu; dry-run kiểm tra cùng các bước chuyển trạng thái với apply.

### Triển khai HTTPS trên máy chủ công ty

- Đặt `DEBUG=False`, `ALLOWED_HOSTS` là tên miền thật và `CSRF_TRUSTED_ORIGINS=https://...` theo địa chỉ người dùng truy cập. Mặc định ứng dụng chuyển HTTP sang HTTPS, đặt cookie đăng nhập/CSRF ở chế độ Secure và HSTS 1 giờ.
- Nếu HTTPS kết thúc ở reverse proxy, chỉ đặt `SECURE_PROXY_SSL_HEADER=True` khi proxy tin cậy đã xóa giá trị `X-Forwarded-Proto` từ client và tự ghi giá trị đúng. Nếu Django nhận HTTPS trực tiếp, để tùy chọn này không bật. Cấu hình sai có thể gây vòng lặp chuyển hướng hoặc tin nhầm HTTP là HTTPS.
- Trên môi trường thử nghiệm, xác nhận `https://.../accounts/login/` trả 200 và tạo cookie Secure; `http://.../accounts/login/` chuyển sang HTTPS. Chạy `manage.py check --deploy`. Chỉ bật HSTS cho mọi subdomain hoặc preload sau khi kiểm kê toàn bộ subdomain của công ty; giữ thời hạn 1 giờ trong giai đoạn đầu rồi tăng sau khi ổn định.

## 4. Backup va ban giao

Backup review chi gom file can review; backup full gom ma nguon, migration, template va tai lieu. Khong dua `.env`, database, du lieu that, `venv`, log, file tam hoac thu muc backups vao ZIP.

Sau moi dot thay doi, ghi vao `docs/PROJECT_PROGRESS.md`: file da sua, test, ket qua dinh luong, rui ro va buoc tiep theo. Chi commit/push khi da kiem tra diff va co yeu cau/uy quyen ro rang.

## 5. Xu ly sai lech thanh toan

Neu nhat ky khac phieu, kiem tra `ChiTietPhieuThanhToan` dang hoat dong. Snapshot phieu la nguon xuat ho so; nhat ky da thanh toan duoc bao ve khoi sua cac truong anh huong tien. Khong xoa cung du lieu de sua nhanh; tao dieu chinh va ghi ly do.
