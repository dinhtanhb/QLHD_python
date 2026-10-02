# QLHD — Quản lý phân bổ, hợp đồng và thanh toán can thiệp

Ứng dụng Django nội bộ của VietHealth quản lý cán bộ can thiệp (CBCT), trẻ, đơn vị, phân bổ chỉ tiêu, phân công, hợp đồng, nhật ký thực hiện và hồ sơ thanh toán cho hoạt động PHCN/CSXH.

**Trạng thái 02/10/2026:** mã nguồn được đối chiếu tại `main`, commit nền `5628f468`. Các luồng chính đã có; đợt bảo trì 01/10 sửa 14 vấn đề về thanh toán, import và gia hạn. Mẫu ĐNTT Word đã bỏ trang trắng, xác minh lại bằng LibreOffice trên fixture. Bộ SQLite mới nhất khám phá 183 test: **180 đạt, 3 test đồng thời cần MySQL bị bỏ qua**. Kết quả MySQL 183/183 trong tiến độ là ghi nhận đợt trước, chưa chạy lại trong phiên này. Xem [tiến độ](docs/PROJECT_PROGRESS.md) và [ba ca UAT](docs/UAT_CURRENT.md) cho bằng chứng và phần còn cần kiểm chứng trên máy vận hành.

## Chức năng hiện có

- Danh mục trẻ, CBCT, đơn vị, nhóm hợp đồng; nhập Excel phân bổ, phân công, hợp đồng và nhật ký.
- Đề xuất, duyệt và quản lý hợp đồng/phụ lục gia hạn; xuất mẫu Word/PDF, nghiệm thu và thanh lý.
- Nhật ký can thiệp, cảnh báo trùng lịch, tính đi lại; sổ phiếu thanh toán và xuất ĐNTT/DSTK/ĐNCK.
- Báo cáo thanh toán theo số HĐ/kỳ, bộ lọc, KPI và xuất Excel; phân quyền theo nhóm tài khoản.

Một CBCT và một số HĐ chỉ có một phiếu hiệu lực trong một kỳ. Thuế của phiếu được tính riêng cho lần thanh toán đó theo cấu hình hiệu lực. Các quyết định và tình huống điều chỉnh được ghi tại [hướng dẫn sử dụng](docs/USER_GUIDE.md).

## Yêu cầu

- Python **3.12+** với bộ phiên bản hiện tại trong `requirements.txt` (`numpy==2.5.2` yêu cầu Python ≥3.12).
- MySQL 8+ (`utf8mb4`, `STRICT_ALL_TABLES`) cho môi trường vận hành. SQLite chỉ dùng cho kiểm thử qua `DB_ENGINE=sqlite`.
- Git và môi trường ảo Python. Mẫu xuất nằm trong `quanly/document_templates/`.

## Cài đặt trên Windows (PowerShell)

Nếu chưa có mã nguồn, clone repository vào thư mục bạn chọn:

```powershell
git clone https://github.com/dinhtanhb/QLHD_python.git D:\QLHD
cd D:\QLHD
```

Nếu đã có `D:\QLHD`, mở PowerShell tại thư mục đó và giữ nguyên `.env` hiện có. Với bản cài mới:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Điền `SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` và các host/origin cần thiết trong `.env`. Dùng tài khoản MySQL riêng cho ứng dụng; không đưa `.env`, dữ liệu thật hoặc khóa API vào Git. Nếu chạy nội bộ bằng HTTP với `DEBUG=False`, đặt `SESSION_COOKIE_SECURE=False` và `CSRF_COOKIE_SECURE=False`; khi triển khai HTTPS, cấu hình cookie và SSL phù hợp.

Chạy migration sau khi đã kiểm tra cấu hình và sao lưu dữ liệu (đặc biệt migration `0033` của sổ phiếu):

```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py createsuperuser
.\venv\Scripts\python.exe manage.py runserver
```

Mở <http://127.0.0.1:8000/>. Xem [hướng dẫn quản trị](docs/ADMIN_MANUAL.md) và [hướng dẫn sử dụng](docs/USER_GUIDE.md) cho luồng hàng ngày.

### Báo cáo và ngày thanh toán

- Báo cáo thanh toán có hai bảng phân trang độc lập, mỗi bảng 15 dòng; dữ liệu chi tiết được đếm/cắt trang trong CSDL. Thanh quyết toán cũng phân trang Nhóm HĐ × Kỳ trực tiếp trong CSDL; KPI và Excel vẫn dùng toàn bộ phạm vi phù hợp.
- Trong bảng tổng hợp theo Số HĐ, Admin có thể mở trang Sửa HĐ hoặc trang chi tiết để xem trước và xác nhận Xóa HĐ. Kế toán/Admin dùng **Lập TT** để mở màn hình tạo phiếu với sẵn hợp đồng, Nhóm HĐ và Kỳ; màn hình này chỉ tạo phiếu cho hợp đồng đã chọn.
- Sau khi tiền đã chuyển, Kế toán/Admin nhập **Ngày thanh toán** rồi bấm **Đã chi** trên sổ phiếu. Ngày hợp lệ được lưu tại phiếu và hiển thị ở cột Ngày thanh toán; phiếu chờ chi hoặc hủy hiển thị dấu gạch ngang. Không có migration mới cho trường này.
- Các cột số căn phải, dùng dấu chấm phân tách hàng nghìn và không lặp ký hiệu tiền ở từng ô. Mã Nhóm HĐ được hiển thị gọn bằng số.
- Nhật ký đã nằm trong phiếu thanh toán hiệu lực chỉ cho sửa ghi chú. Danh sách ẩn nút Xóa đối với nhật ký này; muốn điều chỉnh số liệu cần xử lý phiếu theo quy trình thanh toán.

## Đồng bộ với GitHub trên máy của bạn (PowerShell)

Mở PowerShell, dừng server đang chạy nếu chuẩn bị cập nhật mã rồi tải phiên bản mới nhất:

```powershell
cd D:\QLHD
git status --short
git branch --show-current
git pull --ff-only origin main
```

Các lệnh trên dùng cho bản cài theo hướng dẫn này và nhánh `main`. `--ff-only` sẽ báo lỗi nếu lịch sử local và GitHub đã tách nhánh; hãy kiểm tra các commit trước khi hợp nhất. Nếu `git status --short` báo file bạn đang sửa, hãy hoàn tất hoặc cất các thay đổi đó trước khi pull. `.env` cục bộ không nằm trong Git. Sau khi pull, nếu `requirements.txt` đổi thì cài lại thư viện; nếu có migration mới, sao lưu và kiểm tra dữ liệu trước khi chạy `migrate` theo hướng dẫn quản trị.

Khi **bạn đã sửa và kiểm tra** một tệp muốn đưa lên GitHub, ví dụ `README.md`:

```powershell
cd D:\QLHD
git status --short
git add README.md
git commit -m "Cap nhat README"
git pull --rebase origin main
git push origin main
```

Thay `README.md` trong lệnh `git add` bằng đúng đường dẫn các tệp bạn muốn gửi; kiểm tra `git status --short` để tránh đưa dữ liệu thật lên GitHub. Nếu `git pull --rebase` báo xung đột, xử lý xung đột và chạy `git rebase --continue` trước khi push. GitHub có thể yêu cầu bạn đăng nhập qua trình quản lý thông tin xác thực Git; không dán token vào URL hoặc mã nguồn.

## Kiểm thử không cần MySQL

Trên bản sao mã nguồn, dùng SQLite riêng và đặt `DEBUG=True` trong phiên PowerShell:

```powershell
$env:DB_ENGINE = 'sqlite'
$env:DEBUG = 'True'
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe manage.py test quanly.tests --noinput
.\venv\Scripts\python.exe manage.py test quanly --noinput
```

`quanly.tests` là bộ hồi quy gốc. Lệnh `test quanly` khám phá thêm các module `test_review_*.py` về form, khóa dữ liệu, chuyển sổ và parser; dùng lệnh này để kiểm tra toàn bộ ứng dụng sau bảo trì.

Các lệnh trên không kiểm chứng tương thích MySQL hoặc số liệu trên dữ liệu thật. Hãy UAT trên bản sao MySQL trước khi triển khai. Để rà trạng thái hợp đồng, dùng `python manage.py sync_trang_thai_hop_dong --dry-run`; chỉ dùng `--apply` sau khi đối chiếu danh sách thay đổi. Các lệnh chuyển sổ cũ mặc định dry-run.

## Cấu trúc và quy trình

| Đường dẫn | Vai trò |
|---|---|
| `qlhd/settings.py`, `qlhd/urls.py` | Cấu hình Django và routes |
| `quanly/models.py`, `quanly/views.py`, `quanly/forms.py` | Dữ liệu, màn hình và form nghiệp vụ |
| `quanly/services/`, `quanly/reporting.py`, `quanly/financial.py` | Trạng thái, sổ phiếu, báo cáo và tính tiền |
| `quanly/assignment_import.py`, `quanly/document_export.py`, `quanly/payment_export.py` | Nhập/xuất dữ liệu và văn bản |
| `quanly/templates/`, `quanly/document_templates/` | Giao diện và mẫu hồ sơ |
| `quanly/tests.py`, `quanly/migrations/` | Kiểm thử và lịch sử schema |

Trước mọi thay đổi, đọc [AGENTS.md](AGENTS.md), [quy trình phát triển](docs/DEVELOPMENT_WORKFLOW.md) và [tiến độ](docs/PROJECT_PROGRESS.md). Skill kiểm tra của dự án nằm trong `.cursor/skills/qlhd-change-validation/`, các agent review trong `.cursor/agents/`. `backups/` và `.codex_tmp/` là thư mục cục bộ, không đưa vào Git; `_qa/` còn giữ một số mẫu và script đối chứng cho UAT.
