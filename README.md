# 📋 Hệ Thống Quản Lý Phân Bổ Chỉ Tiêu & Hợp Đồng (QLHD)

**Tên dự án:** Hệ thống Quản lý Phân bổ Chỉ tiêu & Hợp đồng Cán bộ Chuyên trách (CBCT)  
**Đơn vị chủ quản:** Trung tâm Phát triển Sức khỏe Bền vững (VietHealth)  
**Đầu mối kỹ thuật/Phát triển:** Vũ Đình Tân  
**Trạng thái:** Tạm dừng tính năng mới - Đóng băng & Tối ưu mã nguồn (Mốc 3)  

---

## 📖 I. Tổng Quan Dự Án

Hệ thống web nội bộ được xây dựng nhằm số hóa và tự động hóa quy trình quản lý phân bổ chỉ tiêu dịch vụ **Phục hồi chức năng (PHCN)** và **Chăm sóc xã hội (CSXH)** cho Cán bộ chuyên trách (CBCT) tại các địa bàn thuộc dự án của VietHealth.

Hệ thống giải quyết các bài toán cốt lõi:
1. **Tự động hóa tính toán:** Tự động tính giá trị hợp đồng dự kiến dựa trên định mức công lao động (`DON_GIA_CONG`) và phí đi lại (`DMDL_DM1`, `DMDL_DM2`).
2. **Xử lý dữ liệu lớn:** Nhập liệu an toàn từ file phân bổ Excel, tự động làm sạch và chuẩn hóa dữ liệu.
3. **Số hóa quy trình:** Cho phép xem trước, điều chỉnh số buổi thực tế linh hoạt và phê duyệt khởi tạo hợp đồng chính thức (`Số HĐ`, `Ngày ký`, `Thời gian thực hiện`).

---

## 🛠️ II. Công Nghệ & Kiến Trúc Sử Dụng

* **Backend:** Python 3.10+, Django Web Framework (Django ORM, Custom Views, Forms).
* **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5 (Flex/Grid, Modals).
* **Xử lý Dữ liệu:** Pandas, OpenPyXL.
* **Cơ sở dữ liệu:** SQLite (Development) / PostgreSQL (Sẵn sàng cho Production).

---

## 🚀 III. Lộ Trình Phát Triển (Milestones)

Dự án hiện tại đã hoàn thành **~60% tổng khối lượng công việc**.

- [x] **Mốc 1:** Cấu hình hệ thống, quản lý danh mục (Cán bộ, Định mức tài chính).
- [x] **Mốc 2:** Module Import Excel (Chuẩn hóa chuỗi `\xa0`, làm sạch header, preview & lưu tập trung bằng `bulk_create`).
- [x] **Mốc 3:** Quản lý đề xuất & tạo hợp đồng (Bảng 2 dòng song song, Modal Popup sửa số buổi, tự động tính lại kinh phí).
- [ ] **Mốc 4:** Tổng kết, làm sạch dữ liệu rác & tối ưu hiệu năng (Đang thực hiện).
- [ ] **Mốc 5:** Quản lý danh sách Hợp đồng chính thức, cảnh báo thời hạn & Xuất file Word/PDF hợp đồng.
- [ ] **Mốc 6:** Cập nhật nhật ký thực hiện thực tế hàng tháng, đối chiếu chỉ tiêu & Lập bảng kê nghiệm thu.
- [ ] **Mốc 7:** Báo cáo thống kê kinh phí/địa bàn, phân quyền (RBAC) và bàn giao UAT.

---

## ⚙️ IV. Hướng Dẫn Cài Đặt & Chạy Môi Trường Local

### 1. Yêu cầu hệ thống
* Python 3.10+
* Git (Tùy chọn)

### 2. Các bước cài đặt

**Bước 1: Clone mã nguồn về máy**
```bash
git clone <URL_REPOSITORY_CUA_BAN>
cd QLHD
```

**Bước 2: Tạo và kích hoạt môi trường ảo (Virtual Environment)**
* *Trên Windows (PowerShell/CMD):*
```powershell
python -m venv venv
.\venv\Scripts\Activate
```
* *Trên Linux / macOS:*
```bash
python3 -m venv venv
source venv/bin/activate
```

**Bước 3: Cài đặt thư viện phụ thuộc**
```bash
pip install -r requirements.txt
```

**Bước 4: Migrate CSDL & Tạo tài khoản Admin**
```bash
python manage.py migrate
python manage.py createsuperuser
```

**Bước 5: Khởi động Server**
```bash
python manage.py runserver
```
Truy cập hệ thống tại: `http://127.0.0.1:8000/`

---

## 📁 V. Cấu Trúc Mã Nguồn

```text
QLHD/
│
├── quanly/                   # App Django xử lý nghiệp vụ chính
│   ├── models.py             # Cấu trúc DB (CanBo, FinancialConfig, PhanBo...)
│   ├── views.py              # Logic (import_phan_bo, danh_sach_de_xuat...)
│   ├── urls.py               # Routes của hệ thống
│   └── templates/            # Giao diện HTML
│
├── manage.py                 # File thực thi hệ thống
├── requirements.txt          # Danh sách packages
├── .gitignore                # Bỏ qua file rác khi đẩy code
└── README.md                 # Tài liệu dự án
```

---

## 🧹 VI. Lưu Ý Quản Lý & Tối Ưu Dung Lượng

Để dự án luôn nhẹ (dưới 5MB) khi lưu trữ hoặc đẩy lên Git, **luôn cấu hình file `.gitignore`** tại thư mục gốc với nội dung:

```text
# Bỏ qua môi trường ảo (chiếm >200MB)
venv/
.venv/
env/

# Bỏ qua file biên dịch tạm của Python
__pycache__/
*.pyc

# Bỏ qua CSDL nội bộ & file upload
db.sqlite3
media/
*.xlsx
```

*Lưu ý:* Nếu muốn làm sạch máy local, chạy lệnh sau trong PowerShell để xóa toàn bộ file cache tạm:
```powershell
Get-ChildItem -Path . -Filter "__pycache__" -Recurse | Remove-Item -Recurse -Force
```