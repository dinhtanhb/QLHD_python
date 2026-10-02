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
   .\venv\Scripts\python.exe manage.py test quanly --noinput
   ```

4. Đọc các file liên quan và xác định tác động đến dữ liệu, tính tiền, import, export, template và URL.
5. Với thay đổi nghiệp vụ hoặc import/export, phải thực hiện rà soát độc lập bằng các agent trong `.cursor/agents/`.
6. Khi dọn repository, đối chiếu `git ls-files` với các tham chiếu trong mã nguồn và tài liệu. Giữ migration, template, fixture và script dữ liệu có thể còn được vận hành thủ công; không xóa chỉ vì không thấy import Python.

## Sau khi sửa

1. Chạy lại `check`, `makemigrations --check --dry-run`, test liên quan và test hồi quy.
2. Kiểm thử đúng luồng người dùng bị ảnh hưởng trên dữ liệu thực hoặc fixture đại diện.
3. Với HTML: mở trang và kiểm tra lỗi render, bộ lọc, phân trang và bố cục.
4. Với DOCX/XLSX/PDF: mở bằng ứng dụng tương ứng hoặc công cụ kiểm tra định dạng, kiểm tra tên file, số liệu, công thức và nội dung hiển thị.
   Với UAT tạo/sửa/xóa qua giao diện, dùng checklist `docs/UAT_CURRENT.md` trên CSDL riêng; ghi rõ trình duyệt thực sự đã chạy. HTTP test không thay thế kiểm tra JavaScript/bố cục trên Edge. Chạy `test quanly --noinput` để gồm các module `test_review_*.py`, và ghi riêng số test bị bỏ qua.
5. Chạy `git diff --check`, cập nhật `docs/PROJECT_PROGRESS.md` và ghi rõ rủi ro dữ liệu còn lại.
6. Chỉ commit/push theo ủy quyền của người dùng; áp dụng ủy quyền thường trực ở cuối tài liệu này cho các đợt sửa đã hoàn thành.

## Nguyên tắc dữ liệu nghiệp vụ

- Không tự suy diễn rằng một cảnh báo import đồng nghĩa với bản ghi bị bỏ qua; phải phân biệt `thêm`, `cập nhật`, `bỏ qua` và `cảnh báo` bằng số liệu kiểm chứng.
- Khớp dữ liệu phải ưu tiên mã ổn định; chuẩn hóa Unicode, dấu tiếng Việt, khoảng trắng và viết tắt dịch vụ trước khi so sánh.
- Không làm mất nhật ký lịch sử chỉ vì chưa có hợp đồng hiện hành. Các bản ghi lịch sử phải được ghi nhận và hiển thị trạng thái/ghi chú rõ ràng.
- Mọi phép tính thanh toán phải đối chiếu được từ nhật ký -> phân công -> phân bổ/hợp đồng -> lần thanh toán và phải nêu rõ trường hợp không khớp.
- Dữ liệu thật, file Excel, database và thông tin tài khoản không được đưa vào commit nếu không cần thiết.

## Báo cáo kết quả

Mỗi lần bàn giao phải nêu: file đã thay đổi, kiểm thử đã chạy, kết quả định lượng, vấn đề còn lại và việc commit/push có thực hiện hay chưa.

## Quy trình bàn giao mặc định từ 28/09/2026

Theo ủy quyền thường trực của người dùng, sau mỗi đợt sửa mã nguồn, template, migration, import/export hoặc thêm app phải hoàn tất đủ các bước sau:

1. Cập nhật hướng dẫn/quy trình nếu thay đổi ảnh hưởng cách vận hành hoặc kiểm thử.
2. Cập nhật `docs/PROJECT_PROGRESS.md` và các tài liệu nghiệp vụ liên quan.
3. Rà lại skill dự án và chạy các agent review phù hợp trong `.cursor/agents/`; nếu thay đổi import, tài chính hoặc dữ liệu thì bắt buộc dùng cả code review và data-integrity review.
4. Chạy kiểm thử, kiểm tra định dạng và kiểm tra luồng thực tế theo phạm vi thay đổi.
5. Tạo hai bản sao ZIP trong `backups/`: một bản `review` gọn để rà soát và một bản `full` gồm mã nguồn/tài liệu/template; không đưa `.env`, database, dữ liệu thật, `venv`, log hoặc file tạm vào bản sao.
6. Stage đúng các file thuộc đợt thay đổi, tạo commit có mô tả rõ ràng và push lên remote GitHub của nhánh đang làm việc.

Tệp QA có dữ liệu hoặc script chạy tay chỉ được dọn khi đã xác minh mục đích và tác động; `.codex_tmp/`, hồ sơ LibreOffice và tệp khóa `~$*` là tệp tạm, không đưa vào Git hoặc backup. Nếu phát hiện đề xuất đổi tính năng/quy tắc nghiệp vụ, trình người dùng quyết định trước khi triển khai.

Nếu commit hoặc push bị chặn bởi lỗi môi trường/quyền truy cập, phải báo rõ nguyên nhân, commit đã tạo hay chưa và lệnh còn cần người dùng thực hiện; không được coi là hoàn tất khi chưa xác nhận trạng thái remote.
