# Tiến độ dự án QLHD

**Ngày rà soát:** 28/09/2026
**Nhánh:** `main`
**Commit gần nhất:** `a44b66e` – sửa import phân công/hợp đồng/nhật ký và kiểm thử xuất ĐNTT Word ZIP; Excel còn tiếp tục hoàn thiện.
**Trạng thái làm việc:** đang rà soát và chuẩn hóa quy trình; chưa commit thay đổi mới trong lượt này.

**Cập nhật mới nhất:** đã sửa luồng xuất ĐNTT/ĐNCK, chưa commit/push.

## Chuẩn hóa quy trình bàn giao — 28/09/2026

- Người dùng đã ủy quyền mặc định: sau mỗi đợt sửa code/thêm app phải cập nhật hướng dẫn, tiến độ, docs liên quan, skill và agent review phù hợp; chạy kiểm thử; tạo hai bản sao `review`/`full`; sau đó commit và push GitHub.
- Đã ghi quy trình này vào `AGENTS.md`, `docs/DEVELOPMENT_WORKFLOW.md`, skill `.cursor/skills/qlhd-change-validation/SKILL.md` và hai agent review trong `.cursor/agents/`.
- Hai bản sao hiện tại đã được tạo tại `backups/`; không bao gồm `.env`, database, dữ liệu thật, `venv`, log hoặc file tạm.
- Lượt cập nhật quy trình này chưa commit/push tại thời điểm ghi; cần thực hiện commit/push cùng lượt để kiểm tra quy trình mới.

## Admin override dữ liệu khóa phục vụ kiểm thử — 28/09/2026

- Tài khoản quản trị có thể sửa/xóa phân bổ chỉ tiêu và hợp đồng dù `is_locked=True`; bổ sung nút `Mở khóa` cho phân bổ và hợp đồng.
- Admin có thể thêm phân công vào phân bổ đã khóa; các tài khoản nghiệp vụ khác vẫn bị chặn theo quy tắc khóa hiện hành.
- Bổ sung thao tác sửa/xóa phụ lục gia hạn. Khi xóa phụ lục gia hạn đã ký, hệ thống đồng bộ lại ngày kết thúc, giá trị và khối lượng hợp đồng theo phụ lục còn lại hoặc snapshot cũ; quan hệ `PROTECT` vẫn được giữ để không xóa mù hồ sơ liên kết.
- Cập nhật template danh sách/chi tiết để hiển thị đúng thao tác quản trị và không lộ nút admin cho tài khoản thường.
- Kiểm thử: `manage.py check`, `makemigrations --check --dry-run`, SQLite `manage.py test quanly.tests --noinput` đạt **52/52**, `git diff --check` đạt.
- Rủi ro còn lại: xóa hợp đồng/phụ lục có hồ sơ thanh toán hoặc snapshot được bảo vệ vẫn sẽ báo không thể xóa; đây là bảo vệ toàn vẹn dữ liệu, không phải lỗi quyền admin.

## Baseline đã xác minh

- `manage.py check`: đạt.
- `manage.py makemigrations --check --dry-run`: đạt tại lần rà soát.
- `manage.py test quanly.tests`: 21 test đạt.
- Thay đổi chưa commit hiện tại: `quanly/payment_export.py`.
- Đã kiểm thử kỹ thuật file ĐNTT Excel sau sửa: gói ZIP hợp lệ, tải lại được bằng `openpyxl`, mở được bằng Excel COM, và render PDF kiểm tra được.

## Phạm vi đã có bằng chứng hoạt động

- Import và quản lý phân bổ/phân công/hợp đồng/nhật ký với cảnh báo dữ liệu lịch sử.
- Tính toán nhật ký, đi lại, thuế và tổng tiền phục vụ thanh quyết toán.
- Xuất hợp đồng Word/PDF và ĐNTT Word ZIP theo tên file nghiệp vụ.
- Trang danh sách, bộ lọc, KPI và chi tiết hợp đồng đã được cải tiến qua các commit trước.
- ĐNTT Excel có chọn khoảng ngày, bỏ hiển thị số 0 và đã xử lý metadata query-table gây Repair dialog của Excel.
- Trang Đề nghị thanh toán có CBDA mặc định từ danh sách mã `AVH`; lựa chọn được truyền vào DNTT Word, DNTT Excel, DSTK và ĐNCK.
- ĐNCK không còn phụ thuộc external link/add-in `VND()`; số tiền bằng chữ được ghi trực tiếp vào ô hồ sơ.

## Việc đang mở

1. Hoàn thiện và xác nhận toàn bộ yêu cầu ĐNTT Excel trên dữ liệu người dùng: kỳ thanh toán theo kỳ can thiệp, người đề nghị mã `AVH`, khoảng ngày và đối chiếu bảng kê thanh toán.
2. Kiểm thử end-to-end sau khi người dùng import lại hợp đồng: hợp đồng -> nhật ký -> thanh quyết toán -> xuất Word/XLSX.
3. Rà các trường hợp không có hợp đồng hiện hành, hợp đồng đơn vị dạng `DV0001`, gia hạn và dữ liệu lịch sử; không làm mất nhật ký đã import.
4. Bổ sung regression tests cho các lỗi đã gặp: dịch vụ có dấu/không dấu, mã CBCT không có `tinh_id`, thiếu phân công, số lượng kỳ và idempotent import.

## Rủi ro dữ liệu cần giữ nguyên

- Cảnh báo “không tìm thấy phân công/hợp đồng” không tự chứng minh bản ghi bị bỏ qua; cần đối chiếu số `thêm/cập nhật/bỏ qua/cảnh báo` và số bản ghi tồn tại trong DB.
- Một số nhật ký lịch sử có ngày/giờ không đầy đủ hoặc không khớp phân công tại thời điểm hiện tại.
- Dữ liệu hợp đồng có thể chỉ còn trạng thái cuối sau gia hạn; thời hạn lịch sử không thể suy ra đầy đủ nếu thiếu hồ sơ gốc.

## Kết quả rà soát độc lập lần này

Hai agent đã rà code và database, không sửa file:

- Database có 33.937 nhật ký, đủ 14 kỳ; 5.440 dòng không có hợp đồng và vẫn được lưu. Đây là cảnh báo lịch sử, không phải bằng chứng bị bỏ qua.
- Có 91 nhật ký lệch phân bổ so với hợp đồng; có 11 nhóm phân công có khả năng trùng khóa nghiệp vụ, bao phủ 2.632 nhật ký trong 1.154 nhóm. Cần phân biệt trùng dữ liệu với các buổi lặp hợp lệ trước khi dọn dữ liệu.
- Khóa import phân công hiện cần được kiểm tra vì có khả năng chưa bao gồm CBCT; đây là rủi ro gộp nhầm khi cùng trẻ/dịch vụ/nhóm/đợt/kỳ nhưng khác CBCT (`quanly/views.py:966-974`).
- `ChiTietThanhToan.nhat_ky` đang là quan hệ một-một; cần xác nhận lại với nghiệp vụ một CBCT có thể có các lần thanh toán khác nhau.
- Logic đánh số lần thanh toán cần đối chiếu với lịch sử thanh toán thực tế, không chỉ đếm kỳ can thiệp.
- Xuất ĐNTT Excel cần test dữ liệu có nhiều CBCT/hợp đồng/đơn giá trong cùng phạm vi để tránh lấy thông tin địa điểm hoặc đơn giá từ dòng đầu tiên.
- 116 file/artefact đang được Git theo dõi trong `_qa/`; cần quyết định giữ làm bộ kiểm thử hay tách dữ liệu thật/artefact khỏi repository ở một lượt vệ sinh riêng, không tự xóa trong lượt rà soát này.

## Regression tests bắt buộc bổ sung

- Phân công cùng trẻ/dịch vụ/kỳ nhưng khác CBCT không bị gộp.
- Import cùng file hai lần không tăng bản ghi ngoài ý muốn.
- Cảnh báo lịch sử vẫn lưu; chỉ `skipped` khi thực sự không lưu.
- Liên kết đúng cho nhật ký không hợp đồng, hợp đồng đơn vị `DV0001`, hợp đồng CBCT và dịch vụ có dấu/không dấu.
- Một nhật ký không bị thanh toán hai lần hoặc có cơ chế phân bổ nhiều lần thanh toán rõ ràng.
- Xuất Excel nhiều CBCT/nhiều hợp đồng mở được bằng Excel thật và đối chiếu đúng thuế, đi lại, tổng đã thanh toán và số còn lại.

## Xác minh lượt sửa ĐNTT/ĐNCK ngày 28/09/2026

- `manage.py check`: đạt.
- `makemigrations --check --dry-run`: đạt.
- `manage.py test quanly.tests`: 22/22 đạt.
- ĐNCK, DNTT Excel và DSTK mẫu thực tế: ZIP hợp lệ, không còn external links/query tables, `openpyxl` đọc được.
- Excel COM mở thành công cả 3 file kiểm thử, không xuất hiện Repair dialog.
- ĐNCK có số tiền bằng chữ tại `A20`; DNTT Excel ghi CBDA tại vùng “Người đề nghị”; DSTK ghi CBDA tại vùng “Cán bộ dự án”; Word ghi CBDA tại chữ ký “Người đề nghị”.
- `git diff --check`: đạt. Chưa commit/push.

## Quy ước cập nhật

Mỗi lần sửa code hoặc thêm app phải lặp lại `AGENTS.md` và `docs/DEVELOPMENT_WORKFLOW.md`, chạy baseline + test mục tiêu, gọi các agent rà soát phù hợp, rồi cập nhật tài liệu này trước khi bàn giao.

## Xác minh nghiệp vụ đi lại và trùng lịch 28/09/2026

- Đã thêm tính lượt đi lại tự động khi lưu nhật ký: các ca liên tiếp 8-9, 9-10, 10-11 là 1 lượt; 2 ca sáng và 1 ca chiều là 2 lượt.
- PH được gom theo trẻ; CBCT tại `Khác` được gom theo CBCT trong ngày; tại `Trường` CBCT không tính đi lại.
- Đã cho phép lưu nhật ký trùng, gán cờ cảnh báo đỏ, hiển thị danh sách riêng và xuất Excel gửi CBDA xử lý.
- Đã thêm migration `0027_nhatky_conflict_flags.py`; dòng không có giờ không bị ghi đè các giá trị đi lại gốc khi rebuild.
- Khi sửa/điều chuyển phân công, hệ thống rebuild lại các ngày nhật ký liên quan; sửa dòng lịch sử không có giờ vẫn giữ lượt đi lại nguồn.
- Đã thêm lệnh `python manage.py rebuild_nhat_ky_flags` để backfill/rebuild dữ liệu cũ sau khi migrate; có thể giới hạn bằng `--date YYYY-MM-DD`.
- Trạng thái CSDL sau rebuild theo thuật toán mới: 33.937 nhật ký, 14 kỳ, 1.218 dòng đang cảnh báo trùng; 28.100 dòng không có giờ đã giữ/khôi phục giá trị đi lại theo file nguồn.
- Kiểm thử: `manage.py check`, `makemigrations --check --dry-run`, `manage.py test quanly.tests` (26/26) và workbook Excel danh sách trùng 1.218 dòng đọc được bằng `openpyxl`.

## Thanh toán đi lại phụ huynh — 28/09/2026

- Đã chuẩn hóa 3 nhóm hồ sơ theo dữ liệu gốc: `NCS`, `CG`, `CBDA`. `CBDA` được nhận diện từ token `CBDA` trong Ghi chú của trẻ; `Chuyên gia`/`CG` trong Hình thức CT của phân công vào nhóm `CG`; còn lại là `NCS`.
- Không thêm cột Hình thức CT vào nhật ký. Nhật ký trực tiếp và nhật ký import kế thừa từ Phân công trẻ, tránh nhân bản dữ liệu và tránh lệch phân loại; form đã hiển thị hướng dẫn quy tắc.
- Đã bổ sung exporter/routes và nút hồ sơ: `DNTT_NCS`, `DNTT_CG`, `DNTT_CBDA`, `DSTK_NCS`, `DSTK_CG`, `DNCK_NCS`, `DNCK_CG`. `CBDA` không xuất DSTK/DNCK vì ký nhận thủ công.
- Exporter chọn sheet theo tiền tố, xử lý mẫu hiện tại dùng tên sheet hậu tố `_NCS`, bỏ qua ô gộp khi làm sạch dòng, giữ dòng tổng DSTK và ghi công thức tổng DNTT.
- Đã chặn thanh toán trùng lượt của cùng nhật ký giữa nhiều đợt và lọc nhật ký thêm vào đợt theo tháng/năm của đợt.
- Kiểm thử: `manage.py check`, `makemigrations --check --dry-run`, `manage.py test quanly.tests` (31/31), template compile và workbook sinh thử đọc lại được bằng `openpyxl`; chưa commit/push.

Rủi ro còn lại: phân loại CBDA vẫn phụ thuộc nội dung Ghi chú hiện có; cần chuẩn hóa ghi chú trước khi xuất thật. Các file mẫu chỉ có template DNTT cho CBDA, đúng với quy trình ký nhận thủ công. Đã bổ sung ô chọn CBDA mã AVH trước khi xuất và hỗ trợ cột Hình thức CT tùy chọn trong import nhật ký để điền phân công còn thiếu; không tạo cột dư trong bảng nhật ký.

- Sau rà soát bổ sung: khớp phân công có xét Hình thức CT khi file nguồn cung cấp; kiểm tra cùng tháng/năm ở cả form và model; khóa nhật ký bằng transaction khi thêm chi tiết để giảm rủi ro hai request thanh toán cùng lúc.

## Điều hướng TQT đi lại phụ huynh — 28/09/2026

- Đã thêm mục `TQT đi lại phụ huynh` vào menu `Quy trình hợp đồng`.
- Đã thêm nút `Mở TQT đi lại PH` ngay trên trang Nhật ký can thiệp, song song với quy trình TQT công CBCT.
- Đã thêm trang danh sách các đợt TQT đi lại phụ huynh với KPI, bộ lọc nhóm HĐ/trạng thái và liên kết mở chi tiết/xuất hồ sơ theo từng đợt.
- Kiểm tra trên web: route `/thanh-toan-di-lai-phu-huynh/` tải thành công, không có dữ liệu đợt thanh toán nên KPI hiện 0.

## Tạo TQT đi lại theo Nhóm HĐ + Kỳ — 28/09/2026

- Đã chuyển menu TQT đi lại phụ huynh ra ngay dưới menu Thanh quyết toán để đúng luồng nghiệp vụ.
- Đợt TQT đi lại hiện hỗ trợ hai phạm vi: theo Hợp đồng (dữ liệu cũ) hoặc theo Nhóm HĐ + Kỳ can thiệp.
- Đã thêm form tạo theo Nhóm HĐ/Kỳ/tháng/năm; hệ thống tự gom nhật ký có lượt đi lại và trừ phần đã thanh toán trước đó.
- Trang Thanh quyết toán có nút tạo TQT đi lại PH ngay trên từng dòng Nhóm HĐ + Kỳ, có truyền sẵn bộ lọc.
- Kiểm tra web với Nhóm 6, Kỳ 14, tháng 7/2026: xem trước 23 nhật ký/23 lượt; check, migration check, 31/31 test và template compile đều đạt.

## Sửa lỗi tạo và gom TQT đi lại — 28/09/2026

- Nguyên nhân lỗi `Unknown column 'nhom_hd_id'`: CSDL chưa áp dụng migration `0028` sau khi bổ sung phạm vi đợt theo Nhóm/Kỳ.
- Đã chạy thành công migration `0028` và `0029`; toàn bộ migration của app hiện ở trạng thái đã áp dụng.
- Đã thay unique có điều kiện bằng unique thông thường tương thích MySQL; dữ liệu đợt cũ theo Hợp đồng vẫn giữ nguyên.
- Kiểm thử POST tạo/gom theo Nhóm 6, Kỳ 14, tháng 7/2026 trả redirect thành công và đã rollback dữ liệu test.

## Chuẩn hóa mẫu TQT đi lại phụ huynh — 28/09/2026

- Đã đối chiếu trực tiếp các mẫu chuẩn `Mau_DNTT_DiLai_NCS/CG/CBDA.xlsx`, `Mau_DSTK_DiLai_NCS/CG.xlsx` và `Mau_DNCK_DiLai_NCS/CG.xlsx` trong `quanly/document_templates/thanh_toan_di_lai_phu_huynh`.
- ĐNTT Excel đã gom đúng theo CBCT/hợp đồng, sau đó theo trẻ + dịch vụ; không còn ghi lặp từng nhật ký thành một dòng tổng. Với Nhóm 6 + Kỳ 14 + tháng 7/2026, 23 nhật ký của cùng một trẻ/hợp đồng được thể hiện thành một dòng tổng và một dòng chi tiết, tổng thực tế là 23 lượt × 50.000 đồng.
- Đã thêm `Từ ngày` và `Đến ngày` vào đợt thanh toán; mặc định lấy khoảng thời hạn hợp đồng nhưng cho phép sửa trước khi xuất. Khoảng ngày chỉ ghi trên hồ sơ, không lọc lại nhật ký đã gom.
- Địa điểm ĐNTT/DSTK lấy từ xã/phường của các trẻ có phát sinh lượt đi lại, loại trùng. Nếu dữ liệu trẻ chưa có xã/phường, file ghi rõ `Chưa cập nhật xã/phường của trẻ có phát sinh đi lại` thay vì dùng địa điểm chung không có căn cứ.
- Đã thêm migration `0030_dotthanhtoandilaiphuhuynh_date_range.py`; migration đã áp dụng trên CSDL hiện tại.
- Kiểm thử: `manage.py check`, `makemigrations --check --dry-run`, `manage.py test quanly.tests` (31/31), xuất workbook Nhóm 6/Kỳ 14 đọc lại được bằng `openpyxl`; chưa commit/push.

## Sửa phạm vi gom toàn kỳ — 28/09/2026

- Phát hiện lỗi nghiệp vụ: logic cũ lọc thêm tháng/năm ngày can thiệp, nên đợt Nhóm 6–Kỳ 14 chỉ lấy 23 dòng tháng 7, bỏ CBP2026/CBP2022 và các nhật ký tháng 4–6.
- Đã sửa: gom theo toàn bộ Nhóm HĐ + Kỳ; tháng/năm chỉ là kỳ thanh toán hiển thị. Từ ngày–Đến ngày chỉ ghi trên hồ sơ, không lọc nhật ký.
- Khi bấm lại “Tạo và gom nhật ký” với một đợt nhóm đã tồn tại, hệ thống đồng bộ bổ sung phần còn thiếu và không cộng trùng lượt đã thanh toán.
- Đã đồng bộ đợt hiện tại Nhóm 6–Kỳ 14: 100 nhật ký/100 lượt; CBP2211 = 25 lượt; ABP0015: CBP2026 = 6 lượt, CBP2022 = 5 lượt (cùng các dòng hợp lệ khác trong nhóm).
- Kiểm thử web xem trước hiển thị 100 nhật ký/100 lượt; kiểm thử xuất ĐNTT đọc lại được bằng `openpyxl`.

## Gia hạn hợp đồng — 28/09/2026

- Đã đọc và đối chiếu hai mẫu chuẩn trong `quanly/document_templates/phu_luc_gia_han`: gia hạn thời gian và gia hạn khối lượng.
- Đã bổ sung loại phụ lục, ngày kết thúc cũ/mới, tổng tiền tăng thêm/tổng tiền mới và chi tiết khối lượng theo dịch vụ; migration `0031_gia_han_hop_dong.py` đã áp dụng thành công.
- Đã thêm menu `Quy trình hợp đồng > Gia hạn hợp đồng`, danh sách có KPI/lọc, form tạo gia hạn thời gian và gia hạn khối lượng, cùng nút xuất phụ lục Word.
- Đã sửa nút `Thêm khối lượng` trong chi tiết hợp đồng để chuyển sang đúng luồng gia hạn khối lượng; các nút chi tiết hợp đồng được gom theo nhóm: hồ sơ hợp đồng, phụ lục/gia hạn, nhật ký/thanh toán.
- Nếu chọn `Đã ký`, hệ thống đồng bộ ngày kết thúc hoặc giá trị/khối lượng hợp đồng hiện hành; nếu chưa ký, phụ lục vẫn được lưu để rà soát và xuất riêng.
- Kiểm thử: `manage.py check`, `makemigrations --check --dry-run`, `manage.py test quanly.tests` (32/32); kiểm tra web các trang danh sách, form gia hạn và chi tiết hợp đồng; xuất thử hai mẫu Word bằng dữ liệu rollback, không còn placeholder.
- Chưa commit/push. Render PNG tự động của DOCX chưa chạy được vì môi trường thiếu thư viện `pdf2image`; nội dung DOCX đã được đọc lại bằng `python-docx`.

## Điều chỉnh form gia hạn hợp đồng — 28/09/2026

- Đã bỏ ô nhập `Số phụ lục`; hệ thống tự sinh số phụ lục theo loại và số hợp đồng.
- Hai form gia hạn hiển thị `Ngày kết thúc cũ` dạng chỉ đọc; gia hạn khối lượng giữ ngày kết thúc mới bằng ngày cũ, còn gia hạn thời gian vẫn bắt buộc ngày mới lớn hơn ngày cũ.
- Trường `Đã ký` chuyển thành danh sách chọn `Chưa ký/Đã ký`.
- Form gia hạn khối lượng được bố cục lại theo hai nhóm PHCN/CSXH, bổ sung thành tiền từng nhóm, giá trị tăng thêm và tổng giá trị sau tăng; công thức tăng thêm dùng phần số trẻ tăng × số buổi dự kiến × định mức công/đi lại của từng nhóm.
- Kiểm tra web đã xác nhận với hợp đồng 228-26/HĐDV-VH: PHCN 13.500.000, CSXH 27.500.000; tăng 1 trẻ PHCN cho 6 buổi hiển thị tăng thêm 1.500.000 và tổng mới 42.500.000.
- Kiểm thử: `manage.py check`, `makemigrations --check --dry-run`, `manage.py test quanly.tests` (33/33), kiểm tra `git diff --check`; chưa commit/push.

## Chuẩn hóa quyền admin và thao tác sửa/xóa nghiệp vụ — 28/09/2026

- Đã rà lại tài khoản thật trong CSDL: `admin` đang có `is_staff=True` và `is_superuser=True`.
- Đã gom nhận diện admin vào `quanly/permissions.py`; superuser, group `Admin` và tài khoản vận hành `admin` có cờ staff được nhận diện thống nhất ở decorator và template.
- `setup_roles` hiện đồng bộ tài khoản `admin` thành active/staff/superuser nếu môi trường bị thiếu cờ quyền.
- Đã sửa thông báo của `setup_roles` về ASCII để lệnh không lỗi mã hóa CP1252 trên Windows; chạy thực tế trả `Role setup completed.`.
- Bổ sung thao tác quản trị cho Đề xuất hợp đồng, đợt/chi tiết thanh toán CBCT và đợt/chi tiết TQT đi lại phụ huynh: Sửa/Xóa trên giao diện và endpoint POST có CSRF.
- Giữ ràng buộc dữ liệu: không sửa/xóa đề xuất đã tạo hợp đồng; không xóa đợt đã có chi tiết liên kết; không xóa phân bổ/hợp đồng đã khóa hoặc đã phát sinh dữ liệu theo các quy tắc hiện hành.
- Kiểm thử: `manage.py check`, `makemigrations --check --dry-run`, `manage.py test quanly.tests` (35/35), kiểm tra GET các route mới bằng tài khoản `admin` thật (200), `git diff --check` đạt.
- Chưa commit/push.

## Sửa phụ lục gia hạn và đồng bộ trạng thái Đã ký — 28/09/2026

- Gia hạn khối lượng có thêm `Ngày kết thúc mới`, mặc định bằng `Ngày kết thúc cũ`; cho phép giữ nguyên ngày hoặc tăng ngày.
- Admin có route `Sửa` cho cả gia hạn thời gian và gia hạn khối lượng, trong đó có thể đổi `Chưa ký/Đã ký` sau khi phụ lục đã lưu.
- Khi đổi trạng thái, hệ thống đồng bộ lại hợp đồng theo phụ lục đã ký mới nhất: ngày kết thúc, giá trị hợp đồng và khối lượng dịch vụ; khi bỏ ký phụ lục cuối, dữ liệu được phục hồi theo giá trị trước gia hạn.
- Đã kiểm thử thực tế với phụ lục khối lượng hiện có: giá trị hợp đồng `41.000.000 → 48.500.000` khi ký và phục hồi `48.500.000 → 41.000.000` khi bỏ ký; dữ liệu thật đã được rollback về trạng thái ban đầu.
- Kiểm thử: `manage.py check`, `makemigrations --check --dry-run`, `manage.py test quanly.tests` (35/35), GET form tạo/sửa và POST đổi trạng thái bằng tài khoản `admin`; chưa commit/push.

## Chuẩn hóa khổ giấy và lề toàn bộ mẫu xuất — 28/09/2026

- Đã chuẩn hóa 7 mẫu Word trong `quanly/document_templates`: A4, giữ đúng hướng hiện có, lề trên/dưới/trái/phải 20 mm, khoảng đầu/cuối trang 10 mm cho mọi section.
- Đã chuẩn hóa 18 mẫu Excel: A4, lề bốn phía 0.5 inch, fit-to-page theo chiều ngang 1 trang và hướng in rõ ràng: mẫu bảng rộng dọc/ngang theo nghiệp vụ, DNCK/DSTK đi lại dọc, DNTT đi lại và DNTT/DSTK công cán bộ ngang.
- Đã bổ sung script tái sử dụng `scripts/normalize_document_templates.py`; script đặt vùng in chuẩn, ẩn các sheet phụ trợ (`DataStaff`, `Dia diem thuc hien`) và loại bỏ liên kết ngoài còn sót trong mẫu DNCK.
- Đã bổ sung chuẩn hóa page setup runtime trong `quanly/document_export.py` và `quanly/payment_export.py`, cùng vùng in động để dữ liệu mở rộng không bị cắt dòng tổng/phần ký.
- Đã render kiểm tra bằng LibreOffice: tất cả mẫu Word và Excel đều nhận đúng A4; DNTT đi lại ngang, DNCK/DSTK đi lại dọc; không còn metadata external link/query table trong các mẫu Excel.
- Kiểm thử: `manage.py check`, `makemigrations --check --dry-run`, `manage.py test quanly.tests` (36/36), mở lại 18 workbook bằng `openpyxl`, `git diff --check`; chưa commit/push.
- Rủi ro còn lại: mẫu import có nhiều cột vẫn phải kiểm tra khi người dùng tự thêm cột ngoài cấu trúc chuẩn; file khóa tạm `~$Mau_DNTT.xlsx` được bỏ qua khi chuẩn hóa vì không phải template hợp lệ.

## Hoàn thiện Nghiệm thu và Thanh lý hợp đồng — 28/09/2026

- Sửa lỗi POST Nghiệm thu do thiếu import `ChiTietThanhToan` trong `quanly/views.py`.
- Không còn tạo bản ghi nghiệm thu/thanh lý rỗng chỉ khi mở trang; Thanh lý chỉ cho phép sau khi nghiệm thu đã lưu ngày và kết quả đạt.
- Khi lưu Nghiệm thu/Thanh lý, trạng thái hợp đồng được đồng bộ lần lượt thành `NGHIEM_THU`/`THANH_LY`; giá trị nghiệm thu lấy theo tổng chi tiết thanh toán của hợp đồng hoặc giá trị hợp đồng khi chưa có thanh toán.
- Hoàn thiện `quanly/document_export.py`: BBNT gom bảng trẻ + dịch vụ + buổi tại nhà/trường; TLHD gom lịch sử thanh toán theo đợt, thuế TNCN, đi lại, tổng cộng và số còn lại; không còn placeholder trong file xuất.
- Kiểm thử thực tế với hợp đồng `348`: POST nghiệm thu trả redirect và đồng bộ trạng thái trong transaction rollback; xuất thử BBNT/TLHD mở được bằng `python-docx`, render LibreOffice thành 3 trang mỗi mẫu, không lỗi bố cục.
- Kiểm tra thêm hợp đồng `347`: GET form Nghiệm thu không tự tạo bản ghi rỗng; GET Thanh lý khi chưa nghiệm thu trả redirect về chi tiết hợp đồng.
- Đã bổ sung 2 test hồi quy export; tổng test sau sửa đạt `38/38`. Chưa commit/push phần thay đổi này.
- Rủi ro: dữ liệu hiện có một số bản ghi nghiệm thu cũ giá trị `0`; exporter không còn tự suy ngầm sang giá trị hợp đồng/tổng thanh toán, người dùng cần duyệt và lưu lại hồ sơ để cập nhật chính thức.

## Vòng 1 (Codex/P0) — 28/09/2026

- T1: chuẩn hóa `qlhd/settings.py` với parser boolean chịu lỗi, danh sách host/origin từ môi trường, cookie bảo mật, tùy chọn MySQL `utf8mb4`/`STRICT_ALL_TABLES`, log xoay vòng 5 MB × 5; thêm `.env.example` và cập nhật README theo MySQL/non-root/test SQLite.
- T2: `khoa_phan_bo` chỉ nhận POST có CSRF; GET chỉ redirect và phân bổ đã khóa không bị ghi lại.
- T3: thêm service `quanly/services/contract_status.py`, bảng chuyển trạng thái hợp lệ, kiểm tra giá trị nghiệm thu bằng Decimal, GET nghiệm thu/thanh lý không tạo bản ghi rỗng, thanh lý khóa hợp đồng; thêm ba management command báo cáo/đồng bộ.
- T4: thêm `quanly/assignment_import.py`: chỉ nhận `.xlsx` tối đa 10 MB/20.000 dòng, preload danh mục, validate trước khi ghi, atomic all-or-nothing, chế độ chỉ kiểm tra, không tạo trẻ giả, identity có CBCT và báo cảnh báo phân bổ suy/tạo mới. Luồng cũ được giữ tên `_legacy_import_phan_cong` để không làm mất khả năng đối chiếu trong lượt này.
- T5: bổ sung test DB bằng `django.test.TestCase` cho POST khóa phân bổ, quyền route import, vòng đời nghiệm thu/thanh lý, chuyển trạng thái, sửa hợp đồng đã khóa/trái luật, import idempotent/rollback/validate-only, tách CBCT, loại trùng trẻ mới và công thức tiền Decimal; sửa migration cũ để test SQLite không chạy SQL MySQL `MODIFY`.
- T6: cập nhật README/kế hoạch và tài liệu tiến độ. Các thay đổi của lượt này chưa commit/push.

### Kiểm thử Vòng 1

- `DEBUG=True`, `DB_ENGINE=sqlite`: `manage.py check` đạt; `makemigrations --check --dry-run` đạt; `manage.py test quanly.tests`: **49/49 đạt**; `git diff --check` đạt.
- Management command đã kiểm tra cú pháp qua Django check; lệnh đọc dữ liệu cần chạy trên DB đã migrate (không chạy trên SQLite rỗng ngoài test runner).

### Số liệu và rủi ro còn lại

- Không đọc/ghi `.env`, không thay đổi DB thật và không đưa Excel dữ liệu thật vào lượt này.
- Migration `0021_journal_without_contract.py` có thay đổi tương thích SQLite; với MySQL đã áp dụng, nhánh SQL vẫn chỉ chạy trên backend MySQL.
- Cần chạy UAT trên MySQL bản sao sau khi người dùng kiểm tra các file import thật; đặc biệt rà các dòng trẻ mới thiếu ngày sinh/giới tính và các phân bổ CBDA được suy tự động.
- Hai agent review độc lập không phát hiện P0. Các rủi ro P1 còn lại gồm các importer cũ (CBCT/đơn vị/nhật ký/hợp đồng) chưa được chuyển toàn bộ sang atomic trong Vòng 1 và chưa có test MySQL sạch; `import_phan_cong` đã đáp ứng atomic/validate-only theo phạm vi T4. Cấu hình HTTPS/HSTS mặc định cho phép tắt để chạy HTTP nội bộ; production phải bật các biến bảo mật tương ứng.
- Chưa xử lý sổ thanh toán thống nhất, tối ưu TQT quy mô lớn hoặc tách `views.py`; đây là phạm vi Vòng 2–3 theo tài liệu yêu cầu.

## Quyền Admin sửa/xóa dữ liệu khóa phục vụ kiểm thử — 28/09/2026

- Cho phép tài khoản Admin sửa/xóa Phân bổ chỉ tiêu và Hợp đồng kể cả khi bản ghi đang khóa; bổ sung thao tác Mở khóa và hiển thị đúng theo quyền trên các danh sách, chi tiết hợp đồng và danh sách gia hạn.
- Cho phép Admin thêm/sửa/xóa các nghiệp vụ liên quan khi dữ liệu khóa; tài khoản thường bị chặn ở các luồng sửa phân công, điều chuyển, nhật ký, tạo phụ lục và tạo đợt thanh toán.
- Bổ sung xóa phụ lục gia hạn cho Admin. Khi xóa phụ lục đã ký, hệ thống đồng bộ lại ngày kết thúc, giá trị và chi tiết khối lượng; không cho xóa nếu hợp đồng đã phát sinh nghiệm thu, thanh lý hoặc thanh toán để tránh lệch hồ sơ tài chính.
- Đồng bộ dọn các dòng chi tiết khối lượng dịch vụ không còn thuộc phụ lục hiệu lực; khi sửa Hợp đồng, các phụ lục đã ký tiếp tục là nguồn dữ liệu chính cho ngày kết thúc, giá trị và khối lượng.
- Đã bổ sung test quyền và toàn vẹn dữ liệu. Kiểm thử đạt: `manage.py check`, `makemigrations --check --dry-run`, `manage.py test quanly.tests` **54/54**, `git diff --check`.
- Rủi ro còn lại: xóa Hợp đồng có dữ liệu phụ thuộc vẫn bị cơ sở dữ liệu bảo vệ; cần dùng luồng điều chỉnh nghiệp vụ thay vì xóa cưỡng bức. UAT MySQL với dữ liệu thật chưa chạy trong lượt này.
- Bổ sung guard lần cuối cho nghiệm thu/thanh lý, gom thanh toán đi lại theo Nhóm HĐ và cập nhật chi tiết/khoảng ngày; tài khoản thường không thể thao tác tiếp trên HĐ đã khóa hoặc đã thanh lý. Xóa phụ lục đã ký cũng kiểm tra cả các chi tiết thanh toán đi lại theo Nhóm HĐ.
- Bổ sung guard cho thêm chi tiết thanh toán công và tránh xóa toàn bộ chi tiết khối lượng khi phụ lục hiện hành bị thiếu snapshot; các dữ liệu bất thường được giữ lại để Admin xử lý thủ công.
- Admin vẫn toàn quyền trên hồ sơ chưa phát sinh tài chính; sau khi phụ lục đã ký và hợp đồng đã phát sinh nghiệm thu/thanh lý/thanh toán, hệ thống chặn sửa/xóa phụ lục để bảo vệ khả năng đối soát.

## Bổ sung KPI cho các danh mục — 28/09/2026

- Bổ sung khối KPI bố cục responsive cho bốn trang `Trẻ`, `CBCT`, `Nhóm HĐ` và `Đơn vị`; số KPI lấy trên toàn bộ CSDL, không bị thay đổi bởi ô tìm kiếm hoặc phân trang.
- Trang Trẻ hiển thị tổng số, Đồng Nai, Bình Phước và số Nam/Nữ/khác hoặc chưa rõ.
- Trang CBCT hiển thị tổng số, đang hoạt động, địa bàn Đồng Nai/Bình Phước và số Nam/Nữ/khác hoặc chưa rõ.
- Trang Nhóm HĐ hiển thị tổng nhóm, nhóm đang sử dụng, nhóm đã có phân bổ, đã có hợp đồng và chưa có hợp đồng.
- Trang Đơn vị hiển thị tổng số, đang hoạt động, có CBCT, có hợp đồng và chưa có hợp đồng.
- Địa bàn ưu tiên quy ước mã ổn định đang có trong dữ liệu: trẻ `CBP/CDN`, CBCT `ABP/ADN`; các mã khác dùng trường Tỉnh làm fallback. Kiểm tra dữ liệu thật cho thấy 2.165 trẻ hiện chưa gắn bản ghi Tỉnh, nên nếu chỉ đếm theo khóa ngoại Tỉnh sẽ cho KPI địa bàn sai.
- Đã bổ sung test hồi quy kiểm tra context KPI và số đếm địa bàn theo fixture; kiểm thử hiện đạt `55/55`.
- Rủi ro còn lại: khi thêm quy ước mã địa bàn mới cần cập nhật logic fallback hoặc nhập đầy đủ trường Tỉnh để KPI tiếp tục chính xác.

## Sắp xếp Danh mục Đơn vị theo mã — 28/09/2026

- Trang `danh_sach_don_vi` hiện sắp xếp mã đơn vị giảm dần (`-ma_don_vi`), dùng `-id` làm tiêu chí phụ khi mã trùng.
- Bổ sung test hồi quy xác nhận thứ tự danh sách sau phân trang.
- Kiểm thử sau thay đổi: `manage.py check`, `makemigrations --check --dry-run`, `manage.py test quanly.tests` đạt `56/56`.

## Vòng 2 — nền tảng sổ thanh toán thống nhất — 29/09/2026

- Đã sửa các nền tảng độc lập: trạng thái `TAM_DUNG/HUY` không bị đồng bộ ghi đè, dùng `timezone.localdate()`, dry-run kiểm tra chuyển trạng thái, form Hợp đồng không cho chọn thủ công `HET_HAN/NGHIEM_THU/THANH_LY`, cấu hình cookie Secure đọc từ biến môi trường.
- Thêm `quanly/parsing.py` với parser số chặt chẽ và parser tiền VND; import phân công không còn cho CBCT đã tồn tại nhưng thiếu Phân bổ tạo phân công rời.
- Thêm các model `CauHinhThue`, `PhieuThanhToan`, `ChiTietPhieuThanhToan` trong migration `0033` và đăng ký cấu hình thuế/sổ phiếu trong Django Admin.
- Thêm service `quanly/services/payment_ledger.py`: chọn nhật ký chưa thanh toán, bắt buộc HĐ hợp lệ, tính thuế theo từng phiếu, snapshot tiền/thuế, tính lần thanh toán theo phiếu hiệu lực, chặn vượt giá trị HĐ, hủy phiếu mới nhất và xác nhận đã chi.
- Thêm giao diện sổ phiếu, tạo phiếu theo Nhóm HĐ + Kỳ, hủy/xác nhận chi; các URL xuất ĐNTT/DSTK/ĐNCK từ nhật ký chỉ tiếp tục khi nhật ký đã nằm trong phiếu hiệu lực.
- Bảo vệ nhật ký đã thanh toán khỏi sửa các trường ảnh hưởng tiền và khỏi xóa; `recalculate_day` bỏ qua dòng đã thanh toán.
- Test sau đợt nền tảng đạt `60/60`; đã kiểm tra `check` và `makemigrations --check --dry-run` bằng SQLite.
- Dữ liệu thật chưa chạy migration `0033`; cần chạy `migrate` trên bản sao MySQL sau khi review. Không chuyển 151 chi tiết đi lại phụ huynh sang sổ thanh toán công CBCT.

## Vòng 2 - báo cáo và chuyển sổ thanh toán cũ - 29/09/2026

- Bổ sung các lệnh chỉ đọc `bao_cao_nhat_ky_thieu_hop_dong` và `bao_cao_so_thanh_toan` để rà nhật ký thiếu hợp đồng, đối chiếu sổ cũ và sổ phiếu mới.
- Bổ sung `chuyen_so_thanh_toan_cu`: mặc định dry-run, hỗ trợ `--from`, `--to`, chỉ ghi khi có `--force`; bản ghi thiếu hợp đồng/CBCT hoặc đã có chi tiết phiếu mới được báo riêng.
- `_payment_history` của hồ sơ nghiệm thu/thanh lý ưu tiên phiếu thanh toán mới, vẫn fallback sổ cũ để không làm mất khả năng xuất hồ sơ lịch sử. Import phân công cũ trong `views.py` đã được loại bỏ; URL dùng importer chuẩn.
- Kiểm thử bằng SQLite: `manage.py check`, `makemigrations --check --dry-run`, `manage.py test quanly.tests` đạt `60/60`. MySQL test database hiện tại bị tồn trạng thái cũ (duplicate FK/column), cần tạo lại database test sạch khi kiểm thử MySQL.


- Patch cuối Vòng 2: `danh_sach_phieu_thanh_toan` bỏ decorator trùng; tạo phiếu theo Nhóm HĐ + Kỳ nay all-or-nothing bằng `transaction.atomic()`, không ghi dở dang khi một hợp đồng lỗi.
- Kiểm thử lại sau patch: `check`, `makemigrations --check --dry-run`, `manage.py test quanly.tests` đạt `60/60` trên SQLite.
- Cap nhat thuc te 29/09/2026: Moc 1-3 da hoan thanh; Moc 4 da cung co; Moc 5 da co hop dong, gia han, xuat van ban, nghiem thu va thanh ly; Moc 6 da co nhat ky, thanh quyet toan, so thanh toan thong nhat va xuat ho so; Moc 7 da co KPI, RBAC nen tang va bao cao tong hop.
- Dot trien khai tiep theo bo sung `quanly/reporting.py`, route `bao-cao/`, ba sheet Excel (`TongHop`, `TheoNhomKy`, `TheoTreDichVu`) va cac KPI so nhat ky, so buoi, di lai, tien cong, tien di lai.
- Cac file DNTT/DSTK/DNCK dung snapshot tu `ChiTietPhieuThanhToan` hien hanh de tranh sai lech sau khi nhat ky da lap phieu; trang Thanh quyet toan duoc bao ve boi `readonly_required`.
- Kiem thu: `manage.py check` dat; `makemigrations --check --dry-run` dat; `manage.py test quanly.tests --noinput` dat 61/61 tren SQLite.
- Con lai truoc khi dong: tao clone MySQL sach, ap dung migration 0033, chay UAT theo ma tran quyen, mo kiem tra cac file XLSX/DOCX bang ung dung desktop va xac nhan so lieu voi nguoi dung. Khong tu dong thay doi database that.
- Da tao tai lieu ban giao `docs/USER_GUIDE.md` va `docs/ADMIN_MANUAL.md`. Dot nay chua commit/push vi chua co yeu cau ro rang trong luot hien tai.
- UAT MySQL sach da phat hien va sua loi migration 0010: MySQL giu foreign key cu sau khi RenameModel, lam trung ten khi tao lai HopDong. Migration chi go FK cu neu ton tai tren MySQL; SQLite va schema da chuan hoa khong bi anh huong.
- Tao database UAT rieng `qlhd_codex_uat_20260929_c`, chay thanh cong toan bo migration den 0033; `manage.py check`, `makemigrations --check --dry-run` va 62/62 test deu dat tren MySQL. SQLite cung dat 62/62.
- Ba management command bao cao/chuyen so duoc chuan hoa output ASCII an toan voi console Windows cp1252; da chay thanh cong tren UAT rong: 0 nhat ky thieu hop dong, 0 so cu, 0 so moi, 0 dong dry-run.
- Sau dot nay can commit/push migration va command fix; database UAT la moi truong kiem thu, khong phai database van hanh.

## Sua tao phieu theo Nhom HD/Ky va Bao cao hoat dong - 29/09/2026

- Khi tao phieu theo Nhom HD + Ky, hop dong khong co nhat ky moi du dieu kien (chua phat sinh chi phi hoac da thanh toan) duoc bo qua co thong bao; chi loi nghiep vu thuc su moi rollback ca batch.
- Them route alias `/bao-cao-hoat-dong/` cho trang bao cao, doi ten hien thi thanh `Bao cao hoat dong` va giu route `/bao-cao/` de tuong thich nguoc.
- Chuan hoa thong bao batch thanh tieng Viet co dau; cac thong bao co noi dung du lieu van giu nguyen ma hop dong va ly do.
- Kiem thu: SQLite 63/63, MySQL UAT 63/63; check va kiem tra migration dat; hai route bao cao tren server tra redirect dang nhap 302 thay vi 404.

## Tối ưu Thanh quyết toán và đổi Báo cáo thanh toán theo Số hợp đồng - 29/09/2026

- `quanly/reporting.py` đã chuyển sang queryset có `select_related` đầy đủ, tính tiền công/đi lại và phần đã thanh toán bằng biểu thức/subquery SQL; giảm việc truy cập quan hệ lặp trong Python.
- Báo cáo chính được gom theo `Số hợp đồng + Kỳ`, có bộ lọc Số hợp đồng, Năm và giữ các URL cũ `/bao-cao/`, `/bao-cao-hoat-dong/`; bổ sung URL hiển thị `/bao-cao-thanh-toan/` và đổi nhãn menu thành `Báo cáo thanh toán`.
- Bổ sung KPI `Lũy kế năm` và `Lũy kế từ ngày ký hợp đồng`, đồng thời cập nhật xuất Excel theo Số HĐ và hai mốc lũy kế.
- `_journal_export_queryset` của Thanh quyết toán bỏ `prefetch_related` cho FK đơn trị, nạp quan hệ bằng `select_related` và duyệt theo batch để hạn chế N+1 và bộ nhớ.
- Đã bổ sung test lọc theo Số HĐ, tổng lũy kế và route mới; SQLite đạt 63/63 và MySQL UAT sạch `qlhd_codex_uat_20260929_c` đạt 63/63. Lần chạy MySQL đầu phát hiện lỗi alias Subquery không tương thích, đã sửa bằng biểu thức subquery trực tiếp và chạy lại đạt.
- Rủi ro còn lại: màn hình vẫn hiển thị toàn bộ dòng chi tiết trẻ/dịch vụ của phạm vi lọc; nếu dữ liệu tăng rất lớn cần bổ sung phân trang hoặc endpoint tải chi tiết riêng.


## Rà soát hiệu năng/số liệu Báo cáo – Thanh quyết toán – Phiếu (29/09/2026)

Nguồn: bản review `Review_QLHD_Claude.md`. Các bản vá ghi trong review chưa nằm trong mã nguồn bàn giao nên được áp dụng lại và bổ sung kiểm thử trong đợt này.

**Đã sửa**
- `quanly/reporting.py`: viết lại bằng `GROUP BY` ở CSDL (hợp đồng×kỳ, nhóm×kỳ, trẻ×dịch vụ, tổng hợp); không còn `list(queryset)`. Nhóm HĐ hiệu lực tính bằng biểu thức `Case/When` đúng thứ tự của `NhatKyThucHien.nhom_hd_hieu_luc` (nguồn → hợp đồng → phân công → phân bổ); bỏ các nhánh `hop_dong__nhom_hd__isnull` là mã chết vì `HopDong.nhom_hd` bắt buộc.
- `views.thanh_quyet_toan`: gom bằng `GROUP BY`; thuế TNCN đọc từ `CauHinhThue` hiệu lực (`lay_cau_hinh_thue`) thay cho hằng số 5.000.000/10%; bộ lọc Nhóm HĐ dùng nhóm hiệu lực nên khớp Báo cáo.
- `views._journal_export_queryset` và danh sách nhật ký: bộ lọc Nhóm HĐ và CBCT dùng nhóm/CBCT hiệu lực (trước đây bỏ qua tầng hợp đồng).
- `services/payment_ledger.huy_phieu`: chỉ tính phiếu còn hiệu lực khi xác định "lần thanh toán mới nhất".
- `import_phan_bo`/`confirm_import_phan_bo`: chuyển `date`/`Decimal` sang chuỗi trước khi lưu session (session dùng `JSONSerializer`), đọc lại khi xác nhận.
- Tham số GET xấu (`nam=0`, `nam=99999`, `²`, số quá lớn): thêm `parsing.parse_get_int` và `views._is_id`, giá trị không hợp lệ bị bỏ qua thay vì lỗi 500.
- N+1 khi xuất DSTK/ĐNTT: `snapshot_journals` nạp trước các quan hệ; `_eligible_journals` bỏ `.exists()` lặp và `kiem_tra_dieu_kien` không còn truy vấn ngầm qua đối số mặc định của `getattr`.

**Kiểm thử**
- `manage.py check` và `makemigrations --check --dry-run` đạt; SQLite `manage.py test quanly.tests`: **89/89** (63 test cũ + 26 test mới).
- Test mới chạy trên mã cũ thất bại ở các lỗi đã sửa (TQT lọc nhóm/CBCT, thuế theo cấu hình, hủy phiếu, import phân bổ, tham số GET, N+1), còn hai test đối chiếu số liệu báo cáo đạt trên cả mã cũ lẫn mã mới.
- Đo trên SQLite với 8.000 nhật ký: Báo cáo 2,21 s → 0,50 s; Thanh quyết toán 1,38 s → 0,07 s.

**Rủi ro/việc còn lại**
- Chưa chạy trên MySQL UAT; cần chạy lại bộ test và so sánh Báo cáo/TQT trước khi triển khai.
- Chưa xử lý: phiếu bổ sung khi phát sinh nhật ký mới (ràng buộc `uq_phieu_cb_hd_ky_active`, cần quyết định nghiệp vụ); khóa `select_for_update` cho `xac_nhan_chi`/`huy_phieu` khi hai kế toán thao tác đồng thời; cách tính thuế "vượt ngưỡng thì tính trên toàn bộ tiền công" cần người có chuyên môn xác nhận.
- TQT tính thuế theo CBCT gộp nhiều hợp đồng trong cùng Nhóm×Kỳ, còn phiếu tính theo từng hợp đồng nên hai nơi có thể lệch khi một CBCT có nhiều hợp đồng; cần chốt quy tắc.
- `resolve_contract_group` và `assignment_import` còn dùng `str.isdigit()` cho ô Excel (không phải tham số GET).
- Chưa commit/push.

## Làm rõ phiếu đã có trong cùng kỳ — 29/09/2026 (sau commit `5846c06`)

- Chốt nghiệp vụ: mỗi CBCT và số HĐ chỉ có một phiếu hiệu lực trong một kỳ; không tạo phiếu bổ sung. Thuế TNCN tính riêng từng lần thanh toán theo số HĐ, đạt ngưỡng thì tính trên toàn bộ tiền công lần đó, không cộng dồn giữa các phiếu/HĐ. Người dùng kiểm thử MySQL riêng.
- `quanly/services/payment_ledger.py`: khi còn nhật ký đủ điều kiện mà kỳ đã có phiếu hiệu lực, thông báo rõ kỳ, số HĐ, lần thanh toán, trạng thái và số nhật ký chưa đưa vào phiếu. Giữ nguyên từ chối phiếu thứ hai; chỉ hướng dẫn hủy/lập lại nếu phiếu chờ chi và là lần mới nhất. Kỳ không còn nhật ký chưa thanh toán vẫn được bỏ qua.
- `quanly/tests.py`: thêm bốn test cho thông báo/toàn vẹn dữ liệu (kể cả batch rollback), hủy rồi lập lại, kỳ không có nhật ký mới và kỳ khác. Cập nhật `docs/USER_GUIDE.md`, `docs/KE_HOACH_VA_TIEN_DO_DU_AN_VIETHEALTH.md`.
- Hai lượt review độc lập về code và toàn vẹn dữ liệu xác nhận vị trí kiểm tra sau bước lọc nhật ký; dùng từ “chưa được đưa vào phiếu” vì không suy đoán thời điểm nhập nhật ký.
- Baseline SQLite trước sửa: `check`, `makemigrations --check --dry-run`, **96/96** test đạt. Sau sửa: hai lệnh kiểm tra đạt, test mục tiêu **4/4**, toàn bộ `quanly.tests` **100/100** đạt, `git diff --check` đạt.
- Rủi ro còn lại: chưa chạy trên MySQL và dữ liệu vận hành; cần UAT trên bản sao MySQL trước khi áp dụng. Phiếu đã chi không hủy được qua luồng thông thường; xử lý điều chỉnh theo kế toán.

## Rà soát mã nguồn, tài liệu và tệp tạm — 29/09/2026

- `quanly/views.py`: KPI Số CBCT dùng `COUNT DISTINCT` trên cán bộ hiệu lực thay vì tải toàn bộ nhật ký; tên tệp xuất kiểm tra Nhóm HĐ/Kỳ trên toàn phạm vi thay vì chỉ 1.000 dòng đầu. Không đổi công thức tiền hoặc quy tắc tạo phiếu.
- Bổ sung 2 test hồi quy cho nhật ký thứ 1.001 thuộc nhóm khác và số cán bộ hiệu lực trong trang thanh quyết toán. Cập nhật `README.md`, `AGENTS.md`, hướng dẫn phát triển/sử dụng và skill kiểm tra của dự án.
- Xóa 2.885 tệp đã theo dõi: bản sao/đầu ra tạm ở `.codex_tmp/`, đầu ra render và hồ sơ LibreOffice dưới `_qa/`, bản `qlhd/manage.py` trùng với `manage.py` gốc, và tệp khóa Office `~$Mau_DNTT.xlsx`. Giữ 3 script kiểm tra và 3 bảng tính đối chứng trong `_qa/`, toàn bộ migration/mẫu tài liệu có ích và script nhập dữ liệu chạy tay `nhap_dulieu.py`. Thêm quy tắc `.gitignore` cho đầu ra tạm.
- Hai lượt rà soát độc lập xác nhận không có migration, mẫu dùng để xuất, dữ liệu gốc hoặc script QA bị xóa; thứ tự xác định nhóm/cán bộ hiệu lực của dữ liệu lịch sử được giữ nguyên.
- Trước sửa: SQLite `check`, `makemigrations --check --dry-run`, 100/100 test đạt. Sau sửa: hai lệnh kiểm tra đạt, 2/2 test mục tiêu và 102/102 test toàn bộ đạt; `git diff --check` đạt.
- Giới hạn: chưa kiểm thử MySQL và dữ liệu vận hành trong đợt này; cần chạy UAT trên bản sao MySQL trước khi triển khai. Mọi đề xuất đổi tính năng hoặc nghiệp vụ sẽ trình người dùng trước khi thực hiện.

## Hoàn thiện định dạng và thao tác nhật ký đã lập phiếu — 30/09/2026

- Chuẩn hóa số ở thẻ phân công trang chủ và cột kỳ của bảng tóm tắt nhật ký; loại `quanly/report_pages.py` không còn tham chiếu, chứa cấu hình phân trang cũ.
- Nhật ký trong phiếu hiệu lực dùng form ghi chú riêng và chỉ cập nhật cột `ghi_chu`/`updated_at`, không gọi tính lại tiền/đi lại. Danh sách ẩn nút Xóa và thông báo trạng thái; POST xóa trực tiếp trả thông báo thay vì lỗi máy chủ. Vai trò chỉ đọc và người không có quyền trên hợp đồng đã khóa không còn thấy nút sửa/xóa nhật ký.
- Cập nhật README và hướng dẫn sử dụng. Thêm test hồi quy bảo vệ số buổi và snapshot phiếu trước POST thay đổi số liệu, kiểm tra GET và POST xóa.
- Review code và toàn vẹn dữ liệu phát hiện nguy cơ `model.save()` ghi đè tiền/lượt đi lại lịch sử và số lần thanh toán đồng thời; đã chuyển sang cập nhật riêng ghi chú và thêm test có giờ, số tiền lịch sử và hợp đồng đã khóa.
- Baseline trước sửa: SQLite 108/108 test, `check` và kiểm tra migration đạt. Sau sửa: SQLite 111/111 test, `check`, kiểm tra migration và `git diff --check` đạt. Chưa kiểm thử MySQL hoặc dữ liệu vận hành trong đợt này; người dùng sẽ UAT riêng.
