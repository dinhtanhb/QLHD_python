# CLAUDE.md

# QLHD - AI Development Guide

## PURPOSE

QLHD là hệ thống quản lý hợp đồng và thanh toán.

Mục tiêu chính:

- Quản lý hợp đồng
- Quản lý phụ lục
- Quản lý đơn vị
- Quản lý trẻ
- Quản lý cán bộ can thiệp
- Phân công thực hiện
- Nhật ký thực hiện
- Thanh toán
- Báo cáo quản trị

Ưu tiên cao nhất:

1. Tính chính xác dữ liệu
2. Tính ổn định hệ thống
3. Khả năng bảo trì
4. Trải nghiệm người dùng

Tuyệt đối không đánh đổi dữ liệu nghiệp vụ để đổi lấy việc tối ưu kiến trúc.

---

# MANDATORY READING

Trước khi thực hiện bất kỳ thay đổi nào phải đọc:

```text
AGENTS.md
README.md

docs/
```

AGENTS.md là nguồn quy định chính.

Nếu có xung đột:

```text
AGENTS.md
    >
CLAUDE.md
```

---

# PROJECT STACK

Backend:

```text
Django 5.x
Python 3.12+
```

Frontend:

```text
HTML
Bootstrap
JavaScript
```

Database hiện tại:

```text
SQLite
```

Định hướng:

```text
MySQL 8+
```

Tất cả thay đổi mới phải tương thích MySQL.

---

# PROJECT STRUCTURE

## Core Application

```text
quanly/
```

Đây là app nghiệp vụ chính.

Ưu tiên sửa trong app hiện có.

Không tạo app mới nếu chưa thật sự cần thiết.

---

## Project Configuration

```text
qlhd/
```

Bao gồm:

```text
settings.py
urls.py
wsgi.py
asgi.py
```

---

## Documentation

```text
docs/
```

Tài liệu dự án.

Mọi thay đổi lớn cần cập nhật tài liệu tương ứng.

---

## Scripts

```text
scripts/
```

Chứa các script hỗ trợ.

Không đặt nghiệp vụ chính tại đây.

---

# ARCHITECTURE PRINCIPLES

## Ưu tiên sửa thay vì viết lại

Luôn ưu tiên:

✅ Sửa file hiện có

✅ Mở rộng chức năng hiện có

✅ Tái sử dụng code hiện có

Không ưu tiên:

❌ Viết lại toàn bộ module

❌ Refactor chỉ để làm đẹp code

❌ Thay đổi kiến trúc khi chưa cần

---

## Thay đổi tối thiểu

Khi sửa lỗi:

- Chỉ sửa phần gây lỗi
- Hạn chế ảnh hưởng dây chuyền
- Không đổi hành vi nghiệp vụ hiện hữu

---

## Hiểu luồng trước khi sửa

Trước khi sửa:

1. Đọc model liên quan
2. Đọc view liên quan
3. Đọc template liên quan
4. Đọc service liên quan
5. Đánh giá tác động

Không sửa khi chưa hiểu luồng nghiệp vụ.

---

# DATABASE RULES

## Nguyên tắc số 1

Không làm mất dữ liệu.

---

## Không tự thay đổi schema

Không được tự ý:

```text
Xóa bảng

Đổi tên bảng

Đổi tên cột

Xóa cột

Xóa migration
```

trừ khi có yêu cầu rõ ràng.

---

## Migration

Trước khi tạo migration phải:

- Giải thích lý do
- Đánh giá tác động
- Đánh giá dữ liệu hiện hữu

Không tạo migration nếu không thực sự cần thiết.

---

## Tương thích MySQL

Không sử dụng:

- SQL chỉ dành cho SQLite
- Cú pháp đặc thù SQLite
- Logic phụ thuộc SQLite

Ưu tiên code chạy được trên:

```text
SQLite
MySQL
```

---

# BUSINESS DATA RULES

## Dữ liệu thanh toán

Đây là dữ liệu quan trọng nhất.

Mọi thay đổi phải đảm bảo:

```text
Có thể truy vết
```

Từ:

```text
Thanh toán
↓
Nhật ký
↓
Phân công
↓
Hợp đồng
```

---

## Không sửa dữ liệu lịch sử

Không:

```text
Ghi đè lịch sử

Xóa lịch sử

Thay đổi số liệu lịch sử
```

Nếu phát hiện sai:

- Báo cáo
- Giải thích
- Đề xuất hướng xử lý

Không tự sửa dữ liệu.

---

# IMPORT / EXPORT RULES

Nhóm rủi ro cao:

```text
Excel Import

Excel Export

Word Export

PDF Export
```

Bất kỳ thay đổi nào cũng phải:

- Kiểm tra file thực tế
- Kiểm tra dữ liệu đầu vào
- Kiểm tra dữ liệu đầu ra
- Đối chiếu số liệu

Không được giả định file xuất đúng.

---

# REPORTING RULES

Báo cáo phải ưu tiên:

```text
Tính đúng
>
Hiệu năng
>
Giao diện
```

Nếu có mâu thuẫn:

Ưu tiên số liệu chính xác.

---

## Dashboard

Khi phát triển Dashboard:

Ưu tiên:

- KPI rõ ràng
- Bộ lọc đơn giản
- Tốc độ tải nhanh
- Số liệu đối chiếu được

Không thêm biểu đồ nếu không mang giá trị quản trị.

---

# CODING RULES

## Ưu tiên

✅ Hàm ngắn

✅ Tái sử dụng code

✅ Helper function

✅ Service layer

✅ Constants

✅ Logging

---

## Tránh

❌ Magic Number

❌ Hard-code

❌ Hàm quá dài

❌ Logic lặp lại

❌ Query lồng nhau không cần thiết

---

# FILE CREATION POLICY

Đây là quy tắc rất quan trọng.

Không tự tạo:

```text
Nhiều folder mới

Nhiều file mới

App mới

Module mới
```

nếu chỉ để phục vụ việc refactor.

Ưu tiên:

```text
Sửa file hiện có
```

chỉ tạo file mới khi thực sự bắt buộc.

---

# UI RULES

Ưu tiên:

```text
Bootstrap hiện có
```

Không thay đổi toàn bộ giao diện nếu chỉ sửa một chức năng.

Mọi thay đổi UI phải:

- Responsive
- Không phá layout cũ
- Không làm mất chức năng hiện có

---

# PERFORMANCE RULES

Ưu tiên:

- Giảm query
- select_related()
- prefetch_related()
- Pagination

Tránh:

- N+1 Query
- Vòng lặp query trong template
- Tính toán lớn trong giao diện

---

# SECURITY RULES

Kiểm tra:

- Authentication
- Authorization
- CSRF
- Input Validation

Không:

```text
Hard-code password

Hard-code secret key

Hard-code token
```

---

# TESTING REQUIREMENTS

Trước khi kết luận hoàn thành:

## Django Check

```powershell
python manage.py check
```

---

## Migration Check

```powershell
python manage.py makemigrations --check --dry-run
```

---

## Run Tests

```powershell
python manage.py test
```

---

## Manual Verification

Kiểm tra:

- Thêm dữ liệu
- Sửa dữ liệu
- Xóa dữ liệu
- Xuất báo cáo
- Thanh toán
- Dashboard

---

# GIT RULES

Trước khi commit:

```bash
git status
```

Kiểm tra tất cả file thay đổi.

---

Không commit:

```text
.env

venv/

logs/

db.sqlite3

__pycache__/

.codex_tmp/

backups/
```

---

# CHANGE REVIEW PROCESS

Trước mọi thay đổi:

1. Hiểu nghiệp vụ
2. Xác định phạm vi ảnh hưởng
3. Đề xuất phương án
4. Thực hiện thay đổi
5. Kiểm thử
6. Báo cáo kết quả

---

# AI AGENT RULES

Khi hỗ trợ dự án:

Luôn:

✅ Đọc AGENTS.md trước

✅ Phân tích file liên quan

✅ Giải thích tác động

✅ Ưu tiên sửa tối thiểu

✅ Giữ tương thích MySQL

✅ Bảo toàn dữ liệu lịch sử

✅ Kiểm tra trước khi kết luận

---

Không:

❌ Tự ý đổi kiến trúc

❌ Tự ý tạo hàng loạt file

❌ Tự ý đổi database

❌ Tự ý xóa migration

❌ Tự ý xóa dữ liệu

❌ Kết luận hoàn thành khi chưa test

---

# SUCCESS CRITERIA

Một thay đổi chỉ được coi là hoàn thành khi:

✅ Code chạy được

✅ Không phát sinh lỗi Django Check

✅ Không phát sinh migration ngoài ý muốn

✅ Không làm hỏng dữ liệu

✅ Không ảnh hưởng lịch sử

✅ Chức năng cũ vẫn hoạt động

✅ Tài liệu được cập nhật nếu cần

✅ Đã thực hiện kiểm thử tương ứng

---

# DEVELOPMENT PHILOSOPHY

Ưu tiên:

Đúng dữ liệu
>
Ổn định hệ thống
>
Khả năng bảo tr