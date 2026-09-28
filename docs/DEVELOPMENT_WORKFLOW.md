# Quy trình phát triển và kiểm thử QLHD

## Mục đích

Đây là checklist áp dụng lặp lại cho mọi lần sửa mã nguồn hoặc thêm app. `AGENTS.md` là quy tắc ngắn gọn bắt buộc; tài liệu này mô tả cách thực hiện và bằng chứng cần lưu.

## Vòng lặp bắt buộc

### 1. Rà trước khi làm

- Đọc tiến độ hiện tại và kiểm tra nhánh/trạng thái Git.
- Chạy `check`, `makemigrations --check --dry-run` và bộ test hiện có.
- Xác định dữ liệu đầu vào, khóa khớp, tác động tài chính và đầu ra người dùng.
- Nếu liên quan import/export/thanh toán, dùng cả `qlhd-code-reviewer` và `qlhd-data-integrity-reviewer`.

### 2. Sửa trong phạm vi nhỏ

- Giữ thay đổi liên quan cùng một mục tiêu; không xóa hoặc reset thay đổi người dùng.
- Dùng mã ổn định trước tên hiển thị; chuẩn hóa Unicode trước khi so sánh.
- Không biến cảnh báo thành bỏ qua ngầm. Kết quả import phải phân biệt rõ thêm/cập nhật/bỏ qua/cảnh báo.
- Cập nhật test hồi quy cùng lúc với logic mới.

### 3. Xác minh sau khi làm

```powershell
$env:DEBUG = 'True'
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe manage.py test quanly.tests
git diff --check
```

Kiểm thử thêm theo loại thay đổi:

| Phạm vi | Kiểm thử bắt buộc |
|---|---|
| View/URL/template | Mở route, kiểm tra GET/POST, bộ lọc, phân trang, thao tác và bố cục |
| Import | Đếm dòng đầu vào, thêm/cập nhật/bỏ qua, bản ghi lưu thật, cảnh báo và tính lặp lại |
| Tính tiền | Đối chiếu nhật ký, phân công, phân bổ/hợp đồng, thuế, đi lại và lần thanh toán |
| DOCX/PDF | Tên file, placeholder, bảng, tổng tiền và render từng trang |
| XLSX | ZIP hợp lệ, không còn query table lỗi, mở bằng Excel, số 0 hiển thị trống và bộ lọc ngày |
| Model/migration | `makemigrations --check`, test dữ liệu null/duplicate và kiểm tra tương thích dữ liệu cũ |

### 4. Cập nhật hồ sơ

Ghi vào `docs/PROJECT_PROGRESS.md`: ngày, thay đổi, file, kiểm thử, kết quả định lượng, rủi ro và bước tiếp theo.

### 5. Bàn giao mặc định sau mỗi đợt

Theo ủy quyền thường trực của người dùng, sau mỗi đợt thay đổi phải:

- Cập nhật hướng dẫn, tiến độ và tài liệu nghiệp vụ bị ảnh hưởng.
- Rà lại skill dự án và chạy agent review phù hợp; thay đổi import/tài chính phải có cả code review và data-integrity review.
- Tạo hai bản sao ZIP `review` và `full` trong `backups/`, loại trừ `.env`, database, dữ liệu thật, `venv`, log và file tạm.
- Stage có chọn lọc, commit và push lên GitHub sau khi kiểm thử đạt.
- Báo cáo rõ commit, remote/nhánh, file backup, kiểm thử và mọi lỗi push còn tồn tại.

## Lưu ý môi trường Windows

`.env` của môi trường hiện tại có thể đặt `DEBUG` thành giá trị không phải Boolean. Khi chạy kiểm thử local, đặt `$env:DEBUG = 'True'` trong phiên PowerShell hiện tại; không sửa `.env` chỉ để chạy test.
