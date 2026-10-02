# Quy trình phát triển và kiểm thử QLHD

## Mục đích

Đây là checklist áp dụng lặp lại cho mọi lần sửa mã nguồn hoặc thêm app. `AGENTS.md` là quy tắc ngắn gọn bắt buộc; tài liệu này mô tả cách thực hiện và bằng chứng cần lưu.

## Vòng lặp bắt buộc

### 1. Rà trước khi làm

- Đọc tiến độ hiện tại và kiểm tra nhánh/trạng thái Git.
- Chạy `check`, `makemigrations --check --dry-run` và bộ test hiện có.
- Xác định dữ liệu đầu vào, khóa khớp, tác động tài chính và đầu ra người dùng.
- Nếu liên quan import/export/thanh toán, dùng cả `qlhd-code-reviewer` và `qlhd-data-integrity-reviewer`.
- Nếu dọn repository, đếm file theo `git ls-files`, tìm tham chiếu và xác định tệp tạm so với template, migration, script chạy tay và bằng chứng UAT. Không xóa dữ liệu chỉ dựa vào tên thư mục.

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
.\venv\Scripts\python.exe manage.py test quanly --noinput
git diff --check
```

`test quanly` chạy cả bộ gốc và các module `test_review_*.py`; chỉ chạy `quanly.tests` sẽ bỏ sót test bảo vệ mới. Với lệnh chuyển sổ, kiểm tra dry-run và `--force` trên fixture riêng: tổng dòng chọn phải bằng dòng dự kiến chuyển + dòng đã có phiếu + dòng xung đột; lỗi ở nhóm cuối phải rollback cả lượt. Không suy ngày đã chi từ ngày đề nghị. Kiểm tra giao dịch đồng thời trên MySQL riêng khi thay đổi khóa dòng; kiểm tra thứ tự truy vấn trên SQLite chưa đủ chứng minh hành vi đồng thời.

Kiểm thử thêm theo loại thay đổi:

Ba ca UAT tạo/sửa/xóa và luồng phiếu nằm tại [UAT_CURRENT.md](UAT_CURRENT.md). Dùng dữ liệu giả lập hoặc bản sao MySQL tách biệt; kiểm tra lại bản ghi sau mỗi lần lưu. Ghi riêng kiểm thử trình duyệt và kiểm thử HTTP: HTTP không chứng minh JavaScript, select2, hộp xác nhận hay bố cục trên Edge hoạt động. Không ghi “đạt toàn bộ” khi có test bị bỏ qua.

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

Đổi tính năng hoặc quy tắc nghiệp vụ phải được đề xuất để người dùng quyết định trước; đợt bảo trì chỉ sửa lỗi kỹ thuật đã xác minh.

### 5. Bàn giao mặc định sau mỗi đợt

Theo ủy quyền thường trực của người dùng, sau mỗi đợt thay đổi phải:

- Cập nhật hướng dẫn, tiến độ và tài liệu nghiệp vụ bị ảnh hưởng.
- Rà lại skill dự án và chạy agent review phù hợp; thay đổi import/tài chính phải có cả code review và data-integrity review.
- Tạo hai bản sao ZIP `review` và `full` trong `backups/`, loại trừ `.env`, database, dữ liệu thật, `venv`, log và file tạm.
- Chọn file cho backup theo danh sách mã nguồn, tài liệu và template đã rà; loại `.codex_tmp/`, file xuất thử trong `_qa/`, profile LibreOffice và khóa Office `~$*`.
- Stage có chọn lọc, commit và push lên GitHub sau khi kiểm thử đạt.
- Báo cáo rõ commit, remote/nhánh, file backup, kiểm thử và mọi lỗi push còn tồn tại.

## Lưu ý môi trường Windows

### Hồi quy tài chính và import sau rà soát 01/10/2026

- Chạy `test quanly.test_review_fixes` cho 14 lỗi và các ca biên; chạy `test quanly --noinput` trên MySQL riêng/database test để kiểm tra cả khóa dòng đồng thời.
- Khóa tập nhật ký theo PK trước HĐ; mọi bulk update/snapshot chỉ dùng các ID đã khóa, không thêm dòng xuất hiện sau locking read.
- Đối chiếu thuế theo từng phiếu bằng cấu hình khác mặc định và nhiều HĐ cùng CBCT; thử bộ lọc thiếu dòng phiếu, không tự phân bổ thuế hay mở rộng bộ lọc.
- Kiểm tra bảo vệ của cả sổ mới, sổ cũ và đi lại PH; rebuild phải giữ từng kênh riêng và không tính thêm lượt cho ca sớm/nối tiếp mốc đã chốt.
- Import dòng lỗi phải rollback cả phân công tự sinh và cache occurrence. Với HĐ đã chốt, kiểm tra no-op, bộ đếm giữ nguyên và cảnh báo; không reset trạng thái/đơn giá hoặc liên kết lại nhật ký tài chính.
- Khi bỏ ký/xóa/sửa gia hạn, thử có bản nháp và có phụ lục thời gian/khối lượng ký còn lại; bản nháp không làm thay đổi baseline hiện hành.

`.env` của môi trường hiện tại có thể đặt `DEBUG` thành giá trị không phải Boolean. Khi chạy kiểm thử local, đặt `$env:DEBUG = 'True'` trong phiên PowerShell hiện tại; không sửa `.env` chỉ để chạy test.
### Quyền Admin trong giai đoạn kiểm thử

- Admin có thể sửa, xóa và mở khóa phân bổ, hợp đồng và phụ lục để phục vụ UAT.
- Tài khoản thường không được sửa phân công, nhật ký, phụ lục hoặc tạo đợt thanh toán trên hợp đồng/phân bổ đã khóa.
- Không xóa phụ lục đã ký sau khi hợp đồng đã có nghiệm thu, thanh lý hoặc thanh toán; trường hợp này phải tạo hồ sơ điều chỉnh đúng nghiệp vụ.
- Khi bỏ phụ lục đã ký, phải kiểm tra lại ngày kết thúc, giá trị và chi tiết khối lượng hợp đồng sau khi đồng bộ.
