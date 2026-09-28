# Quy tắc làm việc của dự án QLHD

Tài liệu này là quy tắc bắt buộc cho mọi lần sửa mã nguồn, template, migration, import/export hoặc thêm app trong dự án.

## Trước khi sửa

1. Đọc `docs/DEVELOPMENT_WORKFLOW.md` và `docs/PROJECT_PROGRESS.md`.
2. Kiểm tra `git status --short`, nhánh hiện tại và commit gần nhất. Không ghi đè thay đổi có sẵn của người dùng.
3. Chạy baseline bằng môi trường dự án:

   ```powershell
   $env:DEBUG = 'True'
   .\venv\Scripts\python.exe manage.py check
   .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
   .\venv\Scripts\python.exe manage.py test quanly.tests
   ```

4. Đọc các file liên quan và xác định tác động đến dữ liệu, tính tiền, import, export, template và URL.
5. Với thay đổi nghiệp vụ hoặc import/export, phải thực hiện rà soát độc lập bằng các agent trong `.cursor/agents/`.

## Sau khi sửa

1. Chạy lại `check`, `makemigrations --check --dry-run`, test liên quan và test hồi quy.
2. Kiểm thử đúng luồng người dùng bị ảnh hưởng trên dữ liệu thực hoặc fixture đại diện.
3. Với HTML: mở trang và kiểm tra lỗi render, bộ lọc, phân trang và bố cục.
4. Với DOCX/XLSX/PDF: mở bằng ứng dụng tương ứng hoặc công cụ kiểm tra định dạng, kiểm tra tên file, số liệu, công thức và nội dung hiển thị.
5. Chạy `git diff --check`, cập nhật `docs/PROJECT_PROGRESS.md` và ghi rõ rủi ro dữ liệu còn lại.
6. Không commit hoặc push nếu người dùng chưa yêu cầu rõ trong lượt đó.

## Nguyên tắc dữ liệu nghiệp vụ

- Không tự suy diễn rằng một cảnh báo import đồng nghĩa với bản ghi bị bỏ qua; phải phân biệt `thêm`, `cập nhật`, `bỏ qua` và `cảnh báo` bằng số liệu kiểm chứng.
- Khớp dữ liệu phải ưu tiên mã ổn định; chuẩn hóa Unicode, dấu tiếng Việt, khoảng trắng và viết tắt dịch vụ trước khi so sánh.
- Không làm mất nhật ký lịch sử chỉ vì chưa có hợp đồng hiện hành. Các bản ghi lịch sử phải được ghi nhận và hiển thị trạng thái/ghi chú rõ ràng.
- Mọi phép tính thanh toán phải đối chiếu được từ nhật ký -> phân công -> phân bổ/hợp đồng -> lần thanh toán và phải nêu rõ trường hợp không khớp.
- Dữ liệu thật, file Excel, database và thông tin tài khoản không được đưa vào commit nếu không cần thiết.

## Báo cáo kết quả

Mỗi lần bàn giao phải nêu: file đã thay đổi, kiểm thử đã chạy, kết quả định lượng, vấn đề còn lại và việc commit/push có thực hiện hay chưa.
