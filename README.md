# QLHD — Quản lý phân bổ, hợp đồng và thanh toán can thiệp

Ứng dụng Django nội bộ của VietHealth quản lý cán bộ can thiệp (CBCT), trẻ, đơn vị, phân bổ chỉ tiêu, phân công, hợp đồng, nhật ký thực hiện và hồ sơ thanh toán cho hoạt động PHCN/CSXH.

**Trạng thái 29/09/2026:** các luồng nghiệp vụ chính đã có trong mã nguồn. Tiếp tục rà soát dữ liệu lịch sử, kiểm thử MySQL trên bản sao dữ liệu và UAT trước khi áp dụng cho dữ liệu vận hành. Xem [tiến độ và rủi ro](docs/PROJECT_PROGRESS.md) để biết kết quả xác minh theo từng đợt; các kết quả cũ trong tài liệu là lịch sử, không phải kết quả kiểm thử hiện tại.

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

## Kiểm thử không cần MySQL

Trên bản sao mã nguồn, dùng SQLite riêng và đặt `DEBUG=True` trong phiên PowerShell:

```powershell
$env:DB_ENGINE = 'sqlite'
$env:DEBUG = 'True'
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe manage.py test quanly.tests --noinput
```

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
