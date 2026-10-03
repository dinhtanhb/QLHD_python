# UAT hiện hành — 02/10/2026

## Kiểm tra giao diện sau thay đổi 03/10/2026

Trên Edge với CSDL UAT riêng, kiểm tra ba màn hình đại diện: trang tổng quan, danh sách nhật ký can thiệp và trang import phân bổ. Ở kích thước màn hình rộng và hẹp, kiểm tra menu đang chọn, mở nhóm Danh mục/Quy trình hợp đồng, mở/đóng menu di động bằng nút, phím Tab và Escape. Kiểm tra bốn thẻ số liệu, bảng không tràn khỏi vùng hiển thị, màu dòng hợp lệ/lỗi/trùng vẫn phân biệt được, thông báo đóng được. Trên danh sách có nhiều trang, chuyển trang và xác nhận tham số lọc còn giữ nguyên. Chụp ảnh màn hình, ghi kích thước cửa sổ và phiên bản Edge; không dùng dữ liệu vận hành cho thao tác ghi.

Với phương án giao diện A, kiểm tra thêm trang Báo cáo thanh toán và Thanh quyết toán: tiêu đề xanh than dễ đọc trên nền sáng; bộ lọc nằm trong khối riêng và xuống dòng gọn ở các bề rộng 375, 768, 1280 và 1536 px; thẻ số liệu không cắt số tiền; hai bảng báo cáo và bảng thanh quyết toán cuộn ngang khi cần mà không đẩy cả trang tràn màn hình. Kiểm tra nút Lọc/Xóa lọc, Xuất Excel, In ĐNTT và liên kết Lập TT vẫn đúng vị trí, đúng URL; màu đỏ của trùng lịch và màu vàng cảnh báo nghiệp vụ vẫn dễ phân biệt. Đối chiếu ảnh trước/sau của cả ba trang trước khi xác nhận UAT trực quan.

Nguồn kiểm tra: `main` tại `5628f468`. Dùng tài khoản Admin thử nghiệm và CSDL riêng đã áp migration; không trỏ các thao tác tạo/sửa/xóa vào dữ liệu vận hành. Dữ liệu nền cần một CBCT, một trẻ, một phân bổ/phân công VLTL và HĐ đã ký còn hiệu lực trong ngày nhật ký. Đơn giá fixture là 200.000/buổi; giá trị HĐ đủ để lập phiếu.

## Ba ca cần chạy trên Microsoft Edge

| Ca | Thao tác theo luồng | Kết quả phải kiểm tra |
|---|---|---|
| 1. Hồ sơ trẻ chưa liên kết | Đăng nhập → Thêm trẻ với mã UAT riêng → Lưu → tìm theo mã → Sửa tên/điện thoại → Lưu → mở lại → Xóa và xác nhận | Không trùng mã; tên/điện thoại mới được giữ sau tải lại; hồ sơ hết trong danh sách và DB sau xóa |
| 2. Nhật ký chưa thanh toán | Chọn HĐ/phân công hợp lệ → nhập ngày, giờ, 1 buổi → Lưu → Sửa thành 2 buổi và ghi chú → Lưu → mở lại → Xóa và xác nhận | Ngày thuộc thời hạn HĐ; đơn giá lấy từ HĐ; 2 buổi và ghi chú được lưu; nhật ký chưa có thanh toán xóa được |
| 3. Phiếu và dữ liệu đã chi | Thêm nhật ký mới → Lập phiếu theo HĐ/nhóm/kỳ → kiểm tra tiền → Hủy phiếu chờ chi → Lập lại → nhập ngày thanh toán → Đã chi → Sửa ghi chú nhật ký → xem báo cáo | Chỉ một phiếu hiệu lực; ngày chi lưu đúng; chỉ còn ô ghi chú khi sửa nhật ký đã lập phiếu; không có nút Xóa; yêu cầu xóa trực tiếp cũng bị chặn; tiền và số buổi không đổi; báo cáo phản ánh số đã chi |

Khi chạy bằng Edge, kiểm tra thêm ô ngày hiển thị giá trị cũ, select2 chọn đúng HĐ/phân công, hộp xác nhận Xóa/Hủy, thông báo lỗi, phân trang và căn cột số. Ghi phiên bản Edge, phạm vi dữ liệu, ảnh trước/sau và kết quả từng ca. Kiểm tra lại DB bằng tài khoản chỉ đọc để đối chiếu; không tự sửa số liệu để làm test đạt.

## Bằng chứng và giới hạn của phiên 02/10

- Bộ tự động tại `5628f468`: `test quanly --noinput` khám phá 183 test; **180 đạt, 3 test đồng thời cần MySQL bị bỏ qua**. `check`, `makemigrations --check --dry-run` và kiểm tra diff đạt.
- ĐNTT Word: cùng fixture trước/sau sửa mẫu, render LibreOffice giảm 3 xuống 2 trang; đã xem cả hai trang sau sửa. Thuế 300.000, thực nhận 5.700.000, giá trị HĐ 10.000.000, còn lại 4.000.000 giữ nguyên.
- Đã tải gói Microsoft Edge chính thức 154.0.4258.53, nhưng Edge không khởi động do môi trường chặn socket nội bộ (`Operation not permitted`). **Chưa có kết quả kiểm thử giao diện Edge** và chưa truy cập localhost trên máy Windows của người dùng.
- **3/3 ca ở bảng trên đạt** qua GET/POST thật của Django `runserver`, với cookie đăng nhập và CSRF, trên CSDL SQLite giả lập riêng; kết quả được đối chiếu lại bản ghi. Phiếu có tiền công 200.000, ngày đã chi 02/10/2026; ghi chú sửa được, số liệu thanh toán giữ nguyên và yêu cầu xóa nhật ký đã chi bị chặn. Đây là kiểm tra HTTP/nghiệp vụ, không kiểm chứng JavaScript hoặc bố cục trình duyệt.
- Cần chạy lại bằng Edge trên Windows, MySQL và dữ liệu đại diện; kết quả MySQL trong các mục tiến độ cũ là lịch sử, không phải lần chạy mới này.
