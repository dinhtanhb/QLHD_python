# BÁO CÁO KẾ HOẠCH, TIẾN ĐỘ THỰC HIỆN VÀ LỘ TRÌNH HOÀN THÀNH DỰ ÁN
**Dự án:** Hệ thống Quản lý Phân bổ Chỉ tiêu & Hợp đồng Cán bộ Chuyên trách (CBCT)
**Đơn vị triển khai:** Trung tâm Phát triển Sức khỏe Bền vững (VietHealth)
**Ngày cập nhật:** 28/09/2026
**Trạng thái:** Đã triển khai các luồng chính; đang chuẩn hóa an toàn dữ liệu, vòng đời hợp đồng và kiểm thử hồi quy P0

**Ghi chú:** Câu 1: 1 trẻ có thể được phân công cho nhiều CBCT (Cán bộ can thiệp) tùy theo nhu cầu tương ứng với các đợt phân công và hợp đồng cụ thể; Câu 2: 1 CBCT có thể có ký nhiều HĐ trong 1 năm hoặc được gia hạn cả năm, hoặc từ năm này sang năm sau; Câu 3: chỉ theo TỈnh - xã - địa chỉ chi tiết; Câu 4: mỗi tháng sẽ có 1 đợt thanh toán gồm: Đề nghị thanh toán + bảng kê các lần thanh toán (có mẫu word). Khi tới hạn kết thúc HĐ sẽ có Biên bản nghiệm thu & Thanh lý hợp đồng; Câu 5: Admin, Điều phối viên, Kế toán, Cán bộ dự án (CBDA)...
---

> **Cập nhật trạng thái 28/09/2026:** Bảng mốc lịch sử phía dưới được bổ sung từ giai đoạn đầu. Trạng thái thực tế hiện tại, các phần đã triển khai và việc còn lại được quản lý tại [docs/PROJECT_PROGRESS.md](docs/PROJECT_PROGRESS.md); tài liệu đó là nguồn chuẩn cho tiến độ hiện hành.

## I. TỔNG QUAN DỰ ÁN & MỤC TIÊU HỆ THỐNG

### 1. Mục tiêu chung
* **Tự động hóa quản lý chỉ tiêu:** Quản lý việc phân bổ chỉ tiêu Phục hồi chức năng (PHCN) và Chăm sóc xã hội (CSXH) cho Cán bộ chuyên trách (CBCT) tại các huyện/địa bàn thuộc dự án.
* **Chuẩn hóa tính toán tài chính:** Tự động tính toán Giá trị hợp đồng dự kiến dựa trên định mức công lao động (`DON_GIA_CONG`) và định mức chi phí đi lại (`DMDL_DM1`, `DMDL_DM2`).
* **Số hóa quy trình Hợp đồng:** Nhập dữ liệu phân bổ từ Excel, xem trước/kiểm tra lỗi, cho phép điều chỉnh số buổi thực tế, phê duyệt đề xuất và tạo hợp đồng chính thức với số HĐ, ngày ký, thời gian thực hiện.
* **Đảm bảo tính chính xác & Trải nghiệm tốt:** Giao diện trực quan, hỗ trợ hiển thị 2 dòng chỉ tiêu PHCN/CSXH song song, Modal pop-up điều chỉnh số liệu linh hoạt.

### 2. Công nghệ & Kiến trúc
* **Backend:** Python / Django Web Framework, Django ORM, Django Admin / Custom Views.
* **Database:** MySQL 8+ (`utf8mb4`, `STRICT_ALL_TABLES`); SQLite chỉ dùng cho test khi đặt `DB_ENGINE=sqlite`.
* **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5 (Flex/Grid Layout, Modals, Badges, Bootstrap Icons).
* **Xử lý Dữ liệu:** Pandas, OpenPyXL (Đọc, chuẩn hóa chuỗi tiêu đề, xử lý dữ liệu ẩn/đặc biệt từ Excel).

---

## II. LỘ TRÌNH VÀ TIẾN ĐỘ THỰC HIỆN CÁC MỐC (MILESTONES)

```
[Mốc 1: Cấu hình Systems] ---> [Mốc 2: Import Excel] ---> [Mốc 3: Đề xuất & Điều chỉnh HĐ]
                                                                  |
                                                                  v (Hiện tại - Tạm dừng)
[Mốc 6: Nghiệm thu & Bàn giao] <-- [Mốc 5: Thống kê & Báo cáo] <-- [Mốc 4: Quản lý HĐ Chính thức]
```

### Chi tiết các Mốc:

| Mốc | Tên Mốc / Giai đoạn | Trạng thái | Nội dung chính |
|---|---|---|---|
| **Mốc 1** | Cấu hình & Quản lý Danh mục | **Hoàn thành** | Khai báo models `CanBo`, `FinancialConfig`, `PhanBoChiTieu`. Quản lý định mức giá công, phí đi lại. |
| **Mốc 2** | Import Phân bổ từ Excel | **Hoàn thành** | Xây dựng view `import_phan_bo`, chuẩn hóa tiêu đề cột Excel (xóa `\xa0`, khoảng trắng thừa), kiểm tra logic, xem trước preview và lưu tập trung (`bulk_create`). |
| **Mốc 3** | Quản lý Đề xuất & Tạo HĐ | **Hoàn thành** | Xây dựng giao diện `danh_sach_de_xuat`, tính năng Modal Popup sửa số buổi (`sua_phan_bo_chi_tieu`), tự động tính lại giá trị HĐ, tạo HĐ chính thức (`tao_hop_dong_chinh_thuc`). |
| **Mốc 4** | Tổng kết & Đóng băng Nghiệp vụ | **Hoàn thành một phần** | Rà soát mã nguồn, chuẩn hóa template, thêm kiểm thử P0 và hồ sơ tiến độ; chi tiết tại `docs/PROJECT_PROGRESS.md`. |
| **Mốc 5** | Quản lý Hợp đồng Chính thức | **Chờ triển khai** | Trang quản lý danh sách Hợp đồng đã ký, theo dõi thời hạn hợp đồng, xuất file Hợp đồng Word/PDF theo mẫu chuẩn. |
| **Mốc 6** | Theo dõi Tiến độ & Nghiệm thu | **Chờ triển khai** | Quản lý nhật ký thực hiện số buổi thực tế theo tháng/quý; đối chiếu chỉ tiêu HĐ vs Thực tế; lập bảng kê nghiệm thu thanh toán. |
| **Mốc 7** | Báo cáo Thống kê & Phân quyền | **Chờ triển khai** | Báo cáo chi phí theo khu vực/nhóm HĐ; phân quyền người dùng (Admin, Kế toán, Quản lý); kiểm thử toàn diện (UAT) và bàn giao. |

---

## III. TỔNG HỢP CÔNG VIỆC ĐÃ HOÀN THÀNH (DETAILED COMPLETED TASKS)

### 1. Cơ sở Dữ liệu & Xử lý Nghiệp vụ Backend
* [x] **Cấu hình FinancialConfig:** Thiết lập các tham số tài chính cố định gồm `DON_GIA_CONG`, `DON_GIA_DI_LAI_DM1`, `DON_GIA_DI_LAI_DM2`.
* [x] **Mô hình PhanBoChiTieu:** Thiết lập lưu trữ đẩy đủ thông tin chỉ tiêu PHCN (`so_tre_phcn`, `so_buoi_phcn`, `dinh_muc_di_lai_phcn`), CSXH (`so_tre_cs`, `so_buoi_cs`, `dinh_muc_di_lai_cs`), Giá trị hợp đồng dự kiến (`gia_tri_hd_du_kien`), Trạng thái (`DE_XUAT`, `CHO_TAO_HD`, `DA_TAO_HD`).
* [x] **Xử lý Import Excel An toàn (`import_phan_bo`):**
  * Tự động làm sạch tiêu đề cột Excel với `.strip().replace('\xa0', '').replace(' ', '')`.
  * Hàm `get_column_value()` xử lý triệt để các ô trống (`NaN`, `None`, chuỗi rỗng).
  * Ép kiểu an toàn cho số trẻ, số buổi, mã cán bộ chuyên trách (`MaCBCT`).
  * Khớp mã CBCT với DB `CanBo`, hiển thị cảnh báo lỗi chi tiết theo dòng nếu dữ liệu không hợp lệ.
  * Tính toán dự kiến tự động: `Công PHCN + Phí đi lại PHCN + Công CSXH + Phí đi lại CSXH`.
  * Lưu vào Session để Xem trước (Preview) và cho phép xác nhận Lưu tập trung (`bulk_create`).

### 2. Giao diện Người dùng & Thao tác Nghiệp vụ Frontend
* [x] **Trang Danh sách Đề xuất Hợp đồng (`danh_sach_de_xuat.html`):**
  * Thiết kế cấu trúc bảng responsive, hiển thị thông tin khớp 2 dòng rõ ràng cho 2 nhóm chỉ tiêu (PHCN & CSXH).
  * Định dạng tiền tệ VNĐ và phân tách số hàng nghìn chuyên nghiệp.
  * Tích hợp các input `Số HĐ`, `Ngày ký`, `Thời gian thực hiện (Từ ngày - Đến ngày)` cho từng dòng.
* [x] **Chức năng Điều chỉnh / Sửa Số buổi Dự kiến (`sua_phan_bo_chi_tieu`):**
  * Viết view `sua_phan_bo_chi_tieu` nhận dữ liệu số buổi mới, tính lại tổng tiền HĐ dự kiến và cập nhật vào Database.
  * Tích hợp **Modal Popup** điều chỉnh số buổi ngay trên màn hình danh sách.
  * Xử lý tối ưu HTML DOM: Sử dụng thuộc tính `form="form-tao-hd-{{ item.pk }}"` của HTML5 để tránh lỗi lồng thẻ `<form>` trong `<tr>`.
  * Đặt Modal ngoài thẻ `<table>` theo chuẩn Bootstrap 5.
  * Viết hàm JavaScript helper (`openEditModal`, `closeEditModal`) hỗ trợ bật/tắt Popup an toàn trên mọi trình duyệt.

---

## IV. CÁC CÔNG VIỆC CẦN LÀM TIẾP THEO (REMAINING TASKS TO COMPLETION)

### Giai đoạn 1: Quản lý Hợp đồng Chính thức & Xuất Văn bản
* [ ] **Trang Danh sách Hợp đồng Chính thức:** Xem danh sách các HĐ đã tạo, bộ lọc theo Mã CBCT, Nhóm HĐ, Ngày ký, Thời gian thực hiện.
* [ ] **Xuất file Hợp đồng:** Tích hợp tính năng xuất file Word/PDF Hợp đồng dịch vụ cá nhân theo mẫu chuẩn của dự án VietHealth.
* [ ] **Quản lý Trạng thái Hợp đồng:** Cho phép Hủy hợp đồng, Tạm dừng hoặc Điều chỉnh phụ lục hợp đồng.

### Giai đoạn 2: Quản lý Tiến độ Thực hiện & Quyết toán - Nghiệm thu
* [ ] **Nhật ký Thực hiện Thực tế:** Màn hình cho phép cập nhật số buổi thực hiện thực tế hàng tháng của từng CBCT.
* [ ] **Mô-đun Nghiệm thu & Quyết toán:**
  * So sánh Số buổi Hợp đồng vs Số buổi Thực tế thực hiện.
  * Tính toán Giá trị Quyết toán thực tế.
  * Bảng tổng hợp đề nghị thanh toán gửi Kế toán.

### Giai đoạn 3: Báo cáo Thống kê & Dashboards
* [ ] **Báo cáo Tổng hợp Kinh phí:** Thống kê tổng giải ngân theo Huyện, Xã, Nhóm HĐ.
* [ ] **Báo cáo Chỉ tiêu Trẻ:** Thống kê số lượng trẻ PHCN và CSXH đã nhận dịch vụ.
* [ ] **Xuất Báo cáo Excel/PDF:** Cho phép xuất các bảng biểu báo cáo định kỳ phục vụ nhà tài trợ và ban quản lý.

### Giai đoạn 4: Phân quyền, Tối ưu & Bàn giao Dự án
* [ ] **Phân quyền Hệ thống (RBAC):** Phân chia quyền hạn giữa *Admin*, *Quản lý Dự án*, *Kế toán*, *Cán bộ Giám sát Địa bàn*.
* [ ] **Tối ưu Hiệu năng:** Tối ưu hóa câu truy vấn CSDL (`select_related`, `prefetch_related`), tối ưu thời gian nạp trang.
* [ ] **Kiểm thử Toàn diện (UAT):** Chạy thử nghiệm toàn bộ luồng từ Import Excel -> Tạo HĐ -> Nhập thực tế -> Quyết toán thanh toán.
* [ ] **Đóng gói & Bàn giao:** Viết tài liệu Hướng dẫn Sử dụng (User Guide) và tài liệu Quản trị Hệ thống (Admin Manual).

---

## V. ĐÁNH GIÁ & CAM KẾT TIẾN ĐỘ

1. **Đánh giá tiến độ:** Dự án đã hoàn thành **~60% tổng khối lượng công việc**, trong đó toàn bộ phần lõi về cấu hình tài chính, import dữ liệu phức tạp từ Excel và cơ chế đề xuất/điều chỉnh hợp đồng đã vận hành ổn định, chính xác.
2. **Kế hoạch giai đoạn tới:** Sau khi kết thúc giai đoạn tạm dừng, hệ thống sẽ tập trung triển khai Mô-đun Quản lý Hợp đồng Chính thức và Nghiệm thu - Thanh toán.
3. **Mục tiêu hoàn thành:** Đảm bảo toàn bộ hệ thống đi vào vận hành chính thức, sẵn sàng cho công tác quyết toán và báo cáo của VietHealth.
## Cap nhat tien do thuc te - 29/09/2026

Phan trang thai o tren la ke hoach ban dau va khong con phan anh day du ma nguon hien tai. Doi chieu voi repo va ket qua test cho thay:

- Moc 1-3: Hoan thanh.
- Moc 4: Hoan thanh phan cung co an toan, import, trang thai, admin override va tai lieu ky thuat.
- Moc 5: Hoan thanh luong hop dong chinh thuc, gia han thoi gian/khoi luong, xuat Word/XLSX, nghiem thu va thanh ly.
- Moc 6: Hoan thanh luong nhat ky, thanh quyet toan, so thanh toan thong nhat, DNTT/DSTK/DNCK va thanh toan di lai phu huynh; con can UAT tren clone MySQL.
- Moc 7: Hoan thanh KPI danh muc, RBAC nen tang va bao cao tong hop nhat ky; con can UAT, kiem tra file bang ung dung desktop va xac nhan ban giao.

### Giai doan tiep theo da trien khai

- Bao cao tong hop loc theo Nhom HD, Ky, tu ngay/den ngay; xuat Excel gom `TongHop`, `TheoNhomKy`, `TheoTreDichVu`.
- Snapshot du lieu thanh toan khi xuat ho so, tranh sai lech khi nhat ky bi sua sau khi da lap phieu.
- Khoa trang Thanh quyet toan doi voi tai khoan khong du quyen va bo sung test phan quyen.
- Cap nhat huong dan nguoi dung va quan tri tai `docs/USER_GUIDE.md`, `docs/ADMIN_MANUAL.md`.

### Dieu kien dong du an

`check`, `makemigrations --check --dry-run` va 61 test SQLite da dat. Can tao clone MySQL sach, ap dung migration 0033, chay UAT theo ma tran quyen va doi chieu so lieu truoc khi ap dung len database van hanh. Khong tu dong thay doi database that trong giai doan nay.

Cap nhat sau UAT 29/09/2026: da tao database MySQL UAT rieng `qlhd_codex_uat_20260929_c`; toan bo migration den 0033, `check`, `makemigrations --check --dry-run` va 62/62 test da dat tren MySQL. SQLite cung dat 62/62. Da sua migration 0010 de xu ly foreign key cu do RenameModel va sua ba management command de chay an toan tren Windows cp1252. Database van hanh chua bi thay doi.

Cap nhat sua loi 29/09/2026: tao phieu theo Nhom HD + Ky nay bo qua hop dong khong co nhat ky moi du dieu kien, khong rollback ca nhom; them alias `/bao-cao-hoat-dong/` va hien thi tieng Viet co dau. Kiem thu sau sua dat 63/63 tren ca SQLite va MySQL UAT.

Cap nhat 29/09/2026: tối ưu truy vấn Thanh quyết toán; đổi Báo cáo hoạt động thành Báo cáo thanh toán theo Số hợp đồng + Kỳ; thêm lọc HĐ/Năm và KPI lũy kế theo năm, từ ngày ký hợp đồng; cập nhật xuất Excel. SQLite và MySQL UAT sạch đều đạt 63/63.

Quyết định nghiệp vụ 29/09/2026: một CBCT và một số HĐ chỉ có một phiếu hiệu lực cho mỗi kỳ; không lập phiếu bổ sung cùng kỳ. Nếu còn nhật ký chưa đưa vào phiếu, chỉ phiếu chờ chi và là lần mới nhất mới được hủy rồi lập lại. Thuế TNCN tính riêng cho mỗi lần thanh toán theo số HĐ: đạt ngưỡng thì áp tỷ lệ lên toàn bộ tiền công của lần đó, không cộng dồn giữa các phiếu hoặc HĐ. Người dùng tự kiểm thử trên MySQL trước khi áp dụng dữ liệu vận hành.
