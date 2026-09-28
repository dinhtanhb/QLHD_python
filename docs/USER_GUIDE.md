# Huong dan su dung QLHD VietHealth

Tai lieu nay huong dan quy trinh van hanh hang ngay. Cac so lieu tai chinh phai doi chieu tu nhat ky -> phan cong -> phan bo/hop dong -> phieu thanh toan.

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

## 4. Ho so thanh toan

Truoc khi xuat ho so, chon CBDA la nguoi de nghi va chon day du khoang ngay. DNTT/DSTK/DNCK chi lay phieu dang hieu luc. Neu file co so lieu khac man hinh, dung bao cao va chi tiet phieu de truy nguyen truoc khi gui.

## 5. Luu y

- Canh bao import khong dong nghia voi bo qua; xem tong `them`, `cap nhat`, `bo qua`, `canh bao`.
- Khong sua nhat ky da nam trong phieu thanh toan, tru khi Admin xu ly theo quy trinh dieu chinh.
- Khong tu y xoa hop dong/phu luc da phat sinh nghiem thu, thanh ly hoac thanh toan.
- Khi gap loi file Excel, luu lai thong bao repair cua Excel va gui kem ten file, bo loc, Nhom HD, Ky.
