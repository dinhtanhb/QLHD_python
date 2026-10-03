# Huong dan su dung QLHD VietHealth

Tai lieu nay huong dan quy trinh van hanh hang ngay. Cac so lieu tai chinh phai doi chieu tu nhat ky -> phan cong -> phan bo/hop dong -> phieu thanh toan.

## Lưu ý sau bảo trì ngày 01/10/2026

- Hồ sơ ĐNTT/DSTK/ĐNCK lấy thuế và thực nhận của từng phiếu đã chốt. Khi bộ lọc chỉ lấy một phần nhật ký của phiếu, chọn đủ phạm vi phiếu trước khi xuất; hệ thống không tự mở rộng bộ lọc.
- Nhật ký có thanh toán CBCT, sổ cũ hoặc đi lại PH chỉ sửa ghi chú. Phân công liên quan cũng không được đổi định danh/tính tiền, kể cả tài khoản Admin.
- Import HĐ đã chốt hiển thị số dòng **giữ nguyên** và cảnh báo. Muốn rà nhật ký chưa liên kết, dùng danh sách nhật ký thiếu HĐ và đối chiếu riêng; import lại HĐ đã chốt không tự thay hồ sơ lịch sử.
- Nhật ký đã có sổ thanh toán cũ không được lập thêm phiếu mới; sử dụng quy trình chuyển sổ có dry-run và đối chiếu được hướng dẫn trong dự án.
- Chỉ phụ lục đã ký ảnh hưởng ngày, giá trị và khối lượng hiện hành. Gia hạn khối lượng đã ký cập nhật cả ngày kết thúc.
- Dòng nhật ký import lỗi không lưu phân công kỹ thuật kèm theo. Phân biệt số dòng thêm/cập nhật/bỏ qua/giữ nguyên với cảnh báo, và kiểm tra thông báo sau mỗi lượt import.
- Khi import nhật ký với mã nhóm dịch vụ `PHCN` hoặc `CS`, hệ thống dùng dịch vụ cụ thể của phân công đã chọn để nhận diện dòng khi nhập lại. Trong file phân công, Nhóm HĐ ghi rõ phải khớp danh mục (chấp nhận biến thể dấu Unicode và khoảng trắng); giá trị không tìm thấy sẽ báo lỗi thay vì chuyển sang nhóm của CBCT.
- Django Admin chỉ cho xem phiếu thanh toán CBCT và chi tiết phiếu. Việc lập, hủy hoặc xác nhận chi thực hiện trên các màn hình thanh toán để giữ số liệu đối chiếu.
- Nhật ký lịch sử gắn HĐ để liên kết kỹ thuật được phép lập phiếu nếu thỏa các điều kiện lập phiếu còn lại, kể cả khi HĐ liên kết không bao phủ ngày hoặc nhóm nguồn. Trước khi xác nhận đã chi, đối chiếu từng nhật ký với phân công, HĐ, đơn giá và lần thanh toán; không tự gộp nhật ký trùng từ các lần import cũ.

## 1. Khoi dong va dang nhap

Trong PowerShell tai thu muc `D:\QLHD`:

```powershell
.\venv\Scripts\Activate.ps1
$env:DEBUG = 'True'
python manage.py runserver
```

Mo `http://127.0.0.1:8000/` va dang nhap bang tai khoan duoc cap.

## 2. Thu tu xu ly nghiep vu

1. Cap nhat Danh muc Tre, CBCT, Don vi va Nhom HD.
2. Import Phan bo chi tieu, kiem tra canh bao va luu.
3. Import Phan cong, sau do tao De xuat va Hop dong.
4. Nhap Nhat ky can thiep; kiem tra canh bao thieu phan cong, trung lich va cac cot di lai.
5. Tao phieu thanh toan theo Nhom HD + Ky. Chi xuat ho so tu cac nhat ky da nam trong phieu hien hanh.
6. Xuat DNTT/DSTK/DNCK va doi chieu so lieu trong file voi phieu.
7. Lap Nghiem thu, sau do Thanh ly khi ket qua nghiem thu dat.

## 3. Báo cáo thanh toán

Mở menu `Báo cáo thanh toán`, lọc theo `Số hợp đồng` (khóa chính nghiệp vụ), Nhóm HĐ, Kỳ, Năm hoặc khoảng ngày nếu cần. Báo cáo gom theo Số HĐ + Kỳ, gồm KPI nhật ký, buổi, tiền công, đi lại, số đã thanh toán và cảnh báo trùng lịch. `Lũy kế năm` tính từ 01/01 của năm chọn đến ngày kết thúc bộ lọc hoặc ngày hiện tại; `Lũy kế từ ngày ký hợp đồng` tính từ ngày ký của từng hợp đồng đến cùng mốc kết thúc. Nút Excel tạo ba sheet, trong đó sheet tổng hợp và sheet chi tiết đều dùng Số HĐ.

Hai bảng chi tiết Báo cáo thanh toán và danh sách Nhóm HĐ × Kỳ trong Thanh quyết toán đều phân trang 15 dòng bằng truy vấn CSDL; các KPI vẫn tính trên toàn bộ bộ lọc. Thanh quyết toán không gộp nhật ký chưa có số hợp đồng vào số phải lập phiếu; hệ thống vẫn giữ chúng và hiện cảnh báo riêng số nhật ký, số buổi, giá trị cần rà soát/liên kết trước khi thanh toán. TQT đi lại PH gom theo đủ Nhóm×Kỳ và tháng/năm; nếu lọc CBCT hoặc tìm kiếm, nút tạo đợt sẽ ẩn để tránh tạo batch rộng hơn phần đang xem.

## 4. Ho so thanh toan

Truoc khi xuat ho so, chon CBDA la nguoi de nghi va chon day du khoang ngay. DNTT/DSTK/DNCK chi lay phieu dang hieu luc. Neu file co so lieu khac man hinh, dung bao cao va chi tiet phieu de truy nguyen truoc khi gui.

Tên file xuất dùng mã Nhóm HĐ khi toàn bộ nhật ký được chọn thuộc một nhóm; nếu phạm vi có nhiều nhóm, tên file dùng `NTatCa` để tránh hiểu nhầm. KPI “Số CBCT” đếm cán bộ hiệu lực khác nhau trong toàn bộ phạm vi lọc.

Mỗi CBCT và số HĐ chỉ có một phiếu thanh toán hiệu lực trong một kỳ can thiệp. Nếu kỳ đã có phiếu mà còn nhật ký đủ điều kiện chưa được đưa vào phiếu, hệ thống báo số HĐ, lần thanh toán và số nhật ký còn lại; không tạo phiếu bổ sung. Chỉ khi phiếu đang **chờ chi** và là **lần thanh toán mới nhất**, hãy hủy phiếu với lý do rồi lập lại để gộp đủ nhật ký. Phiếu đã chi không thể hủy qua luồng thông thường; chuyển kế toán/Admin xử lý theo quy trình điều chỉnh.

Thuế TNCN được tính riêng trên tiền công của từng lần thanh toán theo một số HĐ. Khi tiền công của lần đó đạt ngưỡng cấu hình, tỷ lệ thuế áp trên toàn bộ tiền công của lần đó; không cộng dồn với hợp đồng hoặc lần thanh toán khác. Kiểm chứng số liệu và căn cứ thuế với bộ phận kế toán trước khi chi trả.

## 5. Luu y

Mẫu ĐNTT Word từ commit `5628f468` đã bỏ đoạn trống thừa trong ô chữ ký. Fixture đã kiểm tra còn hai trang: đề nghị thanh toán và bảng kê; dữ liệu tên/địa chỉ dài vẫn cần xem trước khi in. Các ca kiểm tra lưu, sửa, xóa và phiếu thanh toán được mô tả tại [UAT_CURRENT.md](UAT_CURRENT.md).

- Canh bao import khong dong nghia voi bo qua; xem tong `them`, `cap nhat`, `bo qua`, `canh bao`.
- Nhật ký đã nằm trong phiếu thanh toán hiệu lực chỉ cho sửa ghi chú; các trường số liệu bị khóa và danh sách không hiện nút Xóa. Nếu cần điều chỉnh số liệu, xử lý phiếu theo quy trình thanh toán trước.
- Khong tu y xoa hop dong/phu luc da phat sinh nghiem thu, thanh ly hoac thanh toan.
- Khi gap loi file Excel, luu lai thong bao repair cua Excel va gui kem ten file, bo loc, Nhom HD, Ky.

## Kiểm tra form và import sau đợt bảo trì 01/10/2026

- Đợt thanh toán tháng/năm trùng và chi tiết vượt số buổi/lượt nhật ký hiển thị lỗi trên form; không tạo thêm bản ghi.
- Tài khoản thường không thể chuyển phân công sang phân bổ khóa hoặc nhật ký sang HĐ khóa/thanh lý bằng cách thay lựa chọn trên form. Admin tiếp tục dùng quyền UAT hiện hành.
- Phụ lục đã ký có nghiệm thu, thanh lý hoặc phiếu thanh toán mới được bảo vệ; bỏ chọn “Đã ký” hoặc đổi HĐ không vượt được kiểm tra này.
- Form sửa gia hạn giữ đúng hợp đồng, trạng thái ký và ngày đã lưu. Các ô ngày HTML dùng giá trị ISO để trình duyệt hiển thị được dữ liệu cũ.
- Import phân bổ đánh dấu số trẻ/số buổi âm là không hợp lệ; xác nhận kiểm tra lại quan hệ dữ liệu trước khi lưu. Nếu lượt ghi phân công rollback, số thêm/cập nhật báo bằng 0; chế độ chỉ kiểm tra vẫn báo số dự kiến.
