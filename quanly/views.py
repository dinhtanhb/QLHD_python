import pandas as pd
import numpy as np
import uuid
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from .models import DonVi, Tre, Tinh, Xa, CanBo, NhomHD, HopDong, ChiTieuHopDong, PhanCongTre
from .forms import DonViForm, TreForm, CanBoForm, NhomHDForm
from datetime import date
from django.core.paginator import Paginator
from django.db.models import Q

def clean_empty_excel_value(val):
    """
    Xử lý dữ liệu thô từ Excel:
    Biến mọi ô trống, khoảng trắng, NaN thành kiểu None chuẩn của Python
    để lưu vào Database dưới dạng NULL.
    """
    # Xử lý các giá trị Not-a-Number (NaN) của pandas
    if pd.isna(val):
        return None
    
    # Ép kiểu chuỗi và loại bỏ khoảng trắng 2 đầu
    val_str = str(val).strip()
    
    # Nếu chuỗi rỗng hoặc chứa các chữ đại diện cho rỗng
    if val_str == "" or val_str.lower() in ['nan', 'none', 'null']:
        return None
        
    # Sửa lỗi Excel tự động biến dãy số thành số thực (VD: MST "123456" thành "123456.0")
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
        
    return val_str

# ================================
# TRANG CHỦ (DASHBOARD)
# ================================
def trang_chu(request):
    tong_tre = Tre.objects.count()
    tong_can_bo = CanBo.objects.count()
    tong_don_vi = DonVi.objects.count()
    tong_nhom = NhomHD.objects.count()
    tong_phan_cong = PhanCongTre.objects.count()

    context = {
        'tong_tre': tong_tre,
        'tong_can_bo': tong_can_bo,
        'tong_don_vi': tong_don_vi,
        'tong_nhom': tong_nhom,
    }
    return render(request, 'quanly/trang_chu.html', context)

def lay_danh_sach_xa(request):
    tinh_id = request.GET.get('tinh_id')
    xas = Xa.objects.filter(tinh_id=tinh_id).values('id', 'ten_xa')
    return JsonResponse(list(xas), safe=False)

# ================================
# QUẢN LÝ NHÓM HỢP ĐỒNG
# ================================

def danh_sach_nhom_hd(request):
    ds_nhom = NhomHD.objects.all().order_by('-id')
    return render(request, 'quanly/danh_sach_nhom_hd.html', {'ds_nhom': ds_nhom})

def them_nhom_hd(request):
    if request.method == 'POST':
        form = NhomHDForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã thêm Nhóm hợp đồng thành công!')
            return redirect('danh_sach_nhom_hd')
        else:
            messages.error(request, 'Lưu thất bại! Vui lòng kiểm tra lại biểu mẫu.')
    else:
        form = NhomHDForm()
    return render(request, 'quanly/them_nhom_hd.html', {'form': form})

def sua_nhom_hd(request, id):
    nhom = get_object_or_404(NhomHD, pk=id)
    if request.method == 'POST':
        form = NhomHDForm(request.POST, instance=nhom)
        if form.is_valid():
            form.save()
            messages.success(request, f'Đã cập nhật Nhóm: {nhom.ten_nhom_hd}')
            return redirect('danh_sach_nhom_hd')
        else:
            messages.error(request, 'Cập nhật thất bại, vui lòng kiểm tra lại biểu mẫu.')
    else:
        form = NhomHDForm(instance=nhom)
    return render(request, 'quanly/sua_nhom_hd.html', {'form': form, 'nhom': nhom})

def xoa_nhom_hd(request, id):
    nhom = get_object_or_404(NhomHD, pk=id)
    ten = nhom.ten_nhom_hd
    nhom.delete()
    messages.success(request, f'Đã xóa Nhóm hợp đồng {ten} khỏi hệ thống.')
    return redirect('danh_sach_nhom_hd')

# QUẢN LÝ ĐƠN VỊ
# ================================

def danh_sach_don_vi(request):
    ds_don_vi = DonVi.objects.all().order_by('-id')
    return render(request, 'quanly/danh_sach_don_vi.html', {'ds_don_vi': ds_don_vi})

def them_don_vi(request):
    if request.method == 'POST':
        form = DonViForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã thêm Đơn vị thành công!')
            return redirect('danh_sach_don_vi')
        else:
            messages.error(request, 'Lưu thất bại! Vui lòng kiểm tra lại biểu mẫu.')
    else:
        form = DonViForm()
    return render(request, 'quanly/them_don_vi.html', {'form': form})

def sua_don_vi(request, id):
    don_vi = get_object_or_404(DonVi, pk=id)
    if request.method == 'POST':
        form = DonViForm(request.POST, instance=don_vi)
        if form.is_valid():
            form.save()
            messages.success(request, f'Đã cập nhật Đơn vị: {don_vi.ten_don_vi}')
            return redirect('danh_sach_don_vi')
        else:
            messages.error(request, 'Cập nhật thất bại, vui lòng kiểm tra lại biểu mẫu.')
    else:
        form = DonViForm(instance=don_vi)
    return render(request, 'quanly/sua_don_vi.html', {'form': form, 'don_vi': don_vi})

def xoa_don_vi(request, id):
    don_vi = get_object_or_404(DonVi, pk=id)
    ten = don_vi.ten_don_vi
    don_vi.delete()
    messages.success(request, f'Đã xóa đơn vị {ten} khỏi hệ thống.')
    return redirect('danh_sach_don_vi')

# 1. DANH SÁCH TRẺ
def danh_sach_tre(request):
    # 1. Xử lý tìm kiếm
    query = request.GET.get('q', '')
    if query:
        # Tìm kiếm tương đối (icontains) trên nhiều trường
        danh_sach = Tre.objects.filter(
            Q(ma_tre__icontains=query) |
            Q(ho_ten__icontains=query) |
            Q(ten_phu_huynh__icontains=query) |
            Q(dien_thoai__icontains=query)
        ).order_by('-ma_tre') # Sắp xếp theo mã hoặc ngày tạo tùy bạn
    else:
        danh_sach = Tre.objects.all().order_by('-ma_tre')

    # 2. Xử lý phân trang (15 dòng / trang)
    paginator = Paginator(danh_sach, 15) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
    }
    return render(request, 'quanly/danh_sach_tre.html', context)

# 2. THÊM TRẺ MỚI
def them_tre(request):
    if request.method == 'POST':
        form = TreForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã lưu hồ sơ Trẻ thành công!')
            return redirect('danh_sach_tre')
        else:
            messages.error(request, 'Không thể lưu! Vui lòng kiểm tra lại biểu mẫu.')
    else:
        form = TreForm()
    return render(request, 'quanly/them_tre.html', {'form': form})

# 3. SỬA HỒ SƠ TRẺ
def sua_tre(request, id):
    tre = get_object_or_404(Tre, pk=id)
    if request.method == 'POST':
        form = TreForm(request.POST, instance=tre)
        if form.is_valid():
            form.save()
            messages.success(request, f'Đã cập nhật thành công hồ sơ của {tre.ho_ten}!')
            return redirect('danh_sach_tre')
        else:
            messages.error(request, 'Cập nhật thất bại, vui lòng kiểm tra lại lỗi trên form.')
    else:
        form = TreForm(instance=tre)
    return render(request, 'quanly/sua_tre.html', {'form': form, 'tre': tre})

# 4. XÓA TRẺ
def xoa_tre(request, id):
    tre = get_object_or_404(Tre, pk=id)
    ten_tre = tre.ho_ten
    tre.delete()
    messages.success(request, f'Đã xóa dữ liệu của {ten_tre} khỏi hệ thống.')
    return redirect('danh_sach_tre')

# 5. IMPORT TRẺ
def import_tre(request):
  if request.method == 'POST' and request.FILES.get('file_excel'):
    excel_file = request.FILES['file_excel']
    try:
      df = pd.read_excel(excel_file)
      count_created = 0
      count_updated = 0

      # Lấy danh sách tên các trường hợp lệ của model Tre trong cơ sở dữ liệu
      valid_fields = [f.name for f in Tre._meta.get_fields()]

      for index, row in df.iterrows():
        ma_tre = (
            str(row['MaTre']).strip()
            if pd.notna(row.get('MaTre'))
            else None
        )
        if not ma_tre or ma_tre.lower() == 'nan':
          continue

        ho_ten = (
            str(row['HoTen']).strip() if pd.notna(row.get('HoTen')) else ''
        )
        ngay_sinh = (
            pd.to_datetime(row['NgaySinh']).date()
            if pd.notna(row.get('NgaySinh'))
            else '2015-01-01'
        )
        gioi_tinh = (
            str(row['GioiTinh']).strip()
            if pd.notna(row.get('GioiTinh'))
            else 'Nam'
        )

        # Xây dựng từ điển dữ liệu, chỉ đưa vào các trường thực sự tồn tại trong model Tre
        defaults = {}

        if 'ho_ten' in valid_fields:
          defaults['ho_ten'] = ho_ten
        if 'ngay_sinh' in valid_fields:
          defaults['ngay_sinh'] = ngay_sinh
        if 'gioi_tinh' in valid_fields:
          defaults['gioi_tinh'] = gioi_tinh

        # Các trường phụ huynh / liên lạc nếu có trong file và model
        if pd.notna(row.get('TenPhuHuynh')):
          val = str(row['TenPhuHuynh']).strip()
          for f in ['ten_phu_huynh', 'phu_huynh']:
            if f in valid_fields:
              defaults[f] = val

        if pd.notna(row.get('SdtPhuHuynh')):
          val = str(row['SdtPhuHuynh']).strip()
          # Xử lý trường hợp số điện thoại bị Excel chuyển thành dạng số thập phân (VD: 358115767.0)
          if val.endswith('.0'):
            val = val[:-2]
          for f in ['dien_thoai', 'sdt', 'sdt_phu_huynh']:
            if f in valid_fields:
              defaults[f] = val

        # Bổ sung an toàn cho các trường tài khoản nếu có trong file Excel
        if pd.notna(row.get('TenTaiKhoanPH')):
          val = str(row['TenTaiKhoanPH']).strip()
          if 'ten_tai_khoan' in valid_fields:
            defaults['ten_tai_khoan'] = val
            
        if pd.notna(row.get('SoTaiKhoanPH')):
          val = str(row['SoTaiKhoanPH']).strip()
          for f in ['so_tai_khoan', 'tai_khoan']:
            if f in valid_fields:
              defaults[f] = val
              
        if pd.notna(row.get('NganHangPH')):
          val = str(row['NganHangPH']).strip()
          if 'ngan_hang' in valid_fields:
            defaults['ngan_hang'] = val
            
        if pd.notna(row.get('ChiNhanhPH')):
          val = str(row['ChiNhanhPH']).strip()
          if 'chi_nhanh' in valid_fields:
            defaults['chi_nhanh'] = val

        # Cập nhật đè nếu trùng mã trẻ, hoặc tạo mới nếu chưa có
        obj, created = Tre.objects.update_or_create(
            ma_tre=ma_tre, 
            defaults=defaults
        )
        
        if created:
          count_created += 1
        else:
          count_updated += 1

      messages.success(
          request, 
          f'Import hoàn tất! Đã thêm mới {count_created} trẻ và cập nhật thông tin cho {count_updated} trẻ hiện có.'
      )
      return redirect('danh_sach_tre')

    except Exception as e:
      messages.error(request, f'Lỗi xử lý file Trẻ: {str(e)}')

  return render(request, 'quanly/import_tre.html')


# QUẢN LÝ CÁN BỘ
# ================================

def danh_sach_can_bo(request):
    query = request.GET.get('q', '')
    
    # Tìm kiếm
    if query:
        ds = CanBo.objects.filter(
            Q(ma_can_bo__icontains=query) |
            Q(ho_ten__icontains=query) |
            Q(cccd__icontains=query) |
            Q(dien_thoai__icontains=query) |
            Q(don_vi__ten_don_vi__icontains=query)
        ).order_by('-id')
    else:
        ds = CanBo.objects.all().order_by('-id')

    # Phân trang (15 dòng / trang)
    paginator = Paginator(ds, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
    }
    return render(request, 'quanly/danh_sach_can_bo.html', context)

def them_can_bo(request):
    if request.method == 'POST':
        form = CanBoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã thêm hồ sơ Cán bộ thành công!')
            return redirect('danh_sach_can_bo')
        else:
            messages.error(request, 'Lưu thất bại! Vui lòng kiểm tra lại biểu mẫu.')
    else:
        form = CanBoForm()
    return render(request, 'quanly/them_can_bo.html', {'form': form})

def sua_can_bo(request, id):
    can_bo = get_object_or_404(CanBo, pk=id)
    if request.method == 'POST':
        form = CanBoForm(request.POST, instance=can_bo)
        if form.is_valid():
            form.save()
            messages.success(request, f'Đã cập nhật hồ sơ cán bộ: {can_bo.ho_ten}')
            return redirect('danh_sach_can_bo')
        else:
            messages.error(request, 'Cập nhật thất bại, vui lòng kiểm tra lại biểu mẫu.')
    else:
        form = CanBoForm(instance=can_bo)
    return render(request, 'quanly/sua_can_bo.html', {'form': form, 'can_bo': can_bo})

def xoa_can_bo(request, id):
    can_bo = get_object_or_404(CanBo, pk=id)
    ten = can_bo.ho_ten
    can_bo.delete()
    messages.success(request, f'Đã xóa dữ liệu cán bộ {ten} khỏi hệ thống.')
    return redirect('danh_sach_can_bo')

def import_can_bo(request):
    if request.method == 'POST' and request.FILES.get('file_excel'):
        excel_file = request.FILES['file_excel']
        try:
            df = pd.read_excel(excel_file)
            count_created = 0
            count_updated = 0
            count_skipped = 0

            if df.empty:
                messages.warning(request, 'File Excel không có dữ liệu!')
                return redirect('danh_sach_can_bo')

            # 1. Phát hiện dòng tiêu đề linh hoạt
            cols_str = " ".join([str(c) for c in df.columns]).lower()
            if not any(k in cols_str for k in ['mã', 'macb', 'họ', 'tencb', 'cccd', 'cbct', 'điện thoại']):
                for idx in range(min(10, len(df))):
                    row_vals = [str(v).strip().lower() for v in df.iloc[idx].values if pd.notna(v)]
                    row_str = " ".join(row_vals)
                    if any(k in row_str for k in ['mã', 'macb', 'họ', 'tencb', 'cccd', 'cbct', 'điện thoại']):
                        df.columns = df.iloc[idx]
                        df = df.iloc[idx+1:].reset_index(drop=True)
                        break

            # 2. Hàm lấy giá trị ô Excel
            def get_val(row, possible_names):
                for col in row.index:
                    clean_col = str(col).strip().lower()
                    for name in possible_names:
                        if clean_col == name.strip().lower():
                            return row[col]
                return None

            # 3. Hàm làm sạch dữ liệu ô
            def clean_empty_excel_value(val):
                if pd.isna(val):
                    return None
                val_str = str(val).strip()
                if val_str == "" or val_str.lower() in ['nan', 'none', 'null']:
                    return None
                if val_str.endswith('.0'):
                    val_str = val_str[:-2]
                return val_str

            # 4. Hàm xử lý tự động cấp bản ghi liên kết (Tỉnh, Xã, Đơn vị) không bao giờ bị dính ràng buộc DB
            def get_or_create_related_obj(related_model, search_val, field_name_hint):
                rel_fields = [f.name for f in related_model._meta.get_fields() if not f.is_relation]
                
                target_field = None
                for candidate in [f'ten_{field_name_hint}', 'ten', 'name', f'ten_{related_model._meta.model_name}']:
                    if candidate in rel_fields:
                        target_field = candidate
                        break
                if not target_field:
                    target_field = rel_fields[0] if rel_fields else 'id'

                val_to_use = search_val if search_val else "Chưa xác định"

                # Tìm bản ghi đã có hoặc tạo mới
                obj = related_model.objects.filter(**{target_field: val_to_use}).first()
                if obj:
                    return obj

                create_kwargs = {target_field: val_to_use}
                for rf in related_model._meta.get_fields():
                    if not rf.is_relation and rf.name != target_field and not getattr(rf, 'primary_key', False):
                        if getattr(rf, 'unique', False):
                            create_kwargs[rf.name] = f"AUTO_{uuid.uuid4().hex[:6].upper()}"
                        elif not getattr(rf, 'null', True):
                            if rf.get_internal_type() in ['CharField', 'TextField']:
                                create_kwargs[rf.name] = ""
                            elif rf.get_internal_type() in ['IntegerField', 'BigIntegerField', 'SmallIntegerField']:
                                create_kwargs[rf.name] = 0
                            elif rf.get_internal_type() in ['DateField', 'DateTimeField']:
                                create_kwargs[rf.name] = date(2000, 1, 1)

                return related_model.objects.create(**create_kwargs)

            valid_fields = [f.name for f in CanBo._meta.get_fields()]

            for idx, (_, row) in enumerate(df.iterrows(), start=1):
                try:
                    # LẤY MÃ CÁN BỘ & TÊN
                    ma_raw = get_val(row, ['MaCB', 'Mã CBCT', 'Ma CBCT', 'Mã cán bộ', 'Ma_CBCT', 'MÃ CBCT', 'Mã CB', 'STT', 'Mã'])
                    ten_raw = get_val(row, ['TenCB', 'Họ tên', 'Họ và tên', 'Ho ten', 'Họ và Tên', 'Tên CB'])
                    cccd_raw = get_val(row, ['CCCD', 'Số CCCD', 'CMND', 'Số CMND'])
                    
                    ma_cbct = clean_empty_excel_value(ma_raw)
                    ho_ten = clean_empty_excel_value(ten_raw)
                    cccd = clean_empty_excel_value(cccd_raw)

                    if not ma_cbct and not ho_ten:
                        continue

                    if not ma_cbct:
                        ma_cbct = f"CB_{cccd}" if cccd else f"CB_{idx:04d}"

                    defaults = {}

                    mapping = {
                        'ho_ten': ['TenCB', 'tencb', 'Họ tên', 'Họ và tên', 'Ho ten'],
                        'gioi_tinh': ['GioiTinh', 'gioitinh', 'Danh xưng', 'Giới tính', 'Gioi tinh'],
                        'cccd': ['CCCD', 'Số CCCD', 'CMND'],
                        'dien_thoai': ['DienThoai', 'dienthoai', 'Điện thoại', 'SĐT', 'Số điện thoại'],
                        'email': ['Email', 'Hòm thư'],
                        'mst': ['MSTCN', 'mstcn', 'MST', 'Mã số thuế'],
                        'tinh': ['Tinh', 'Tỉnh', 'Tỉnh/Thành phố'],
                        'xa': ['Xa', 'Xã', 'Xã/Phường'],
                        'dia_chi': ['DiaChi', 'diachi', 'Địa chỉ', 'Dia chi'],
                        'so_tai_khoan': ['TaiKhoanNH', 'taikhoannh', 'Số tài khoản', 'STK'],
                        'ngan_hang': ['TenNH', 'tennh', 'Ngân hàng', 'Ngan hang'],
                        'chi_nhanh': ['ChiNhanhNH', 'chinhanhnh', 'Chi nhánh', 'Chi nhanh'],
                        'don_vi': ['DonViCongTac', 'donvicongtac', 'Đơn vị công tác', 'Đơn vị']
                    }

                    for db_field, col_candidates in mapping.items():
                        if db_field in valid_fields:
                            val_raw = get_val(row, col_candidates)
                            clean_val = clean_empty_excel_value(val_raw)
                            field_obj = CanBo._meta.get_field(db_field)
                            is_null_allowed = getattr(field_obj, 'null', True)

                            # 1. Nếu là Cột Khóa Ngoại (Foreign Key như Tỉnh, Xã, Đơn vị)
                            if field_obj.is_relation and field_obj.related_model is not None:
                                related_model = field_obj.related_model
                                if clean_val is not None:
                                    defaults[db_field] = get_or_create_related_obj(related_model, clean_val, db_field)
                                else:
                                    if is_null_allowed:
                                        defaults[db_field] = None
                                    else:
                                        # Bắt buộc phải có FK -> Tự động gắn vào "Chưa xác định"
                                        defaults[db_field] = get_or_create_related_obj(related_model, "Chưa xác định", db_field)

                            # 2. Nếu là Cột Dữ Liệu Thường (Text, Số, Ngày)
                            else:
                                if clean_val is not None:
                                    defaults[db_field] = clean_val
                                else:
                                    if is_null_allowed:
                                        defaults[db_field] = None
                                    else:
                                        internal_type = field_obj.get_internal_type()
                                        if internal_type in ['CharField', 'TextField']:
                                            defaults[db_field] = ""
                                        elif internal_type in ['IntegerField', 'BigIntegerField', 'SmallIntegerField']:
                                            defaults[db_field] = 0
                                        elif internal_type in ['DateField', 'DateTimeField']:
                                            defaults[db_field] = date(2000, 1, 1)
                                        else:
                                            defaults[db_field] = None

                    # Xử lý Ngày cấp & Nơi cấp CCCD
                    ngay_cap_raw = get_val(row, ['NgayCapCCCD', 'ngaycapcccd', 'Ngày cấp CCCD', 'Ngày cấp'])
                    ngay_cap_clean = clean_empty_excel_value(ngay_cap_raw)
                    if 'ngay_cap_cccd' in valid_fields:
                        field_ngay = CanBo._meta.get_field('ngay_cap_cccd')
                        is_null_ngay = getattr(field_ngay, 'null', True)
                        if ngay_cap_clean:
                            try:
                                defaults['ngay_cap_cccd'] = pd.to_datetime(ngay_cap_clean).date()
                            except Exception:
                                defaults['ngay_cap_cccd'] = None if is_null_ngay else date(2000, 1, 1)
                        else:
                            defaults['ngay_cap_cccd'] = None if is_null_ngay else date(2000, 1, 1)

                    noi_cap_raw = get_val(row, ['NoiCapCCCD', 'noicapcccd', 'Nơi cấp CCCD', 'Nơi cấp'])
                    noi_cap_clean = clean_empty_excel_value(noi_cap_raw)
                    if 'noi_cap_cccd' in valid_fields:
                        field_noi = CanBo._meta.get_field('noi_cap_cccd')
                        is_null_noi = getattr(field_noi, 'null', True)
                        if noi_cap_clean:
                            defaults['noi_cap_cccd'] = noi_cap_clean
                        else:
                            defaults['noi_cap_cccd'] = None if is_null_noi else ""

                    # Lưu hoặc cập nhật Cán bộ
                    obj, created = CanBo.objects.update_or_create(
                        ma_can_bo=ma_cbct,
                        defaults=defaults
                    )

                    if created:
                        count_created += 1
                    else:
                        count_updated += 1

                except Exception:
                    # Bỏ qua dòng bị lỗi để toàn bộ file vẫn tiếp tục import bình thường
                    count_skipped += 1
                    continue

            msg = f'Import hoàn tất! Thêm mới: {count_created}, Cập nhật: {count_updated}.'
            if count_skipped > 0:
                msg += f' (Bỏ qua {count_skipped} dòng lỗi)'
            messages.success(request, msg)
            return redirect('danh_sach_can_bo')

        except Exception as e:
            messages.error(request, f'Lỗi xử lý file Excel: {str(e)}')

    return render(request, 'quanly/import_can_bo.html')

# CÁC HÀM XỬ LÝ HỢP ĐỒNG & PHÂN CÔNG
# ==========================================

def import_phan_cong(request):
  if request.method == 'POST' and request.FILES.get('file_excel'):
    excel_file = request.FILES['file_excel']
    try:
      df = pd.read_excel(excel_file)

      for index, row in df.iterrows():
        # 1. Xử lý thông tin Trẻ (Lấy theo IDChild)
        ma_tre = str(row['IDChild']).strip()
        ten_tre = (
            str(row['Tên trẻ']).strip() if pd.notna(row['Tên trẻ']) else ''
        )
        tre, _ = Tre.objects.get_or_create(
            ma_tre=ma_tre, defaults={'ho_ten': ten_tre}
        )

        # 2. Xử lý Cán bộ can thiệp (Mã CB)
        ma_cb = str(row['Mã CB']).strip()
        ten_cb = str(row['Tên CB']).strip() if pd.notna(row['Tên CB']) else ''
        can_bo, _ = CanBo.objects.get_or_create(
            ma_can_bo=ma_cb,
            defaults={
                'ho_ten': ten_cb,
                'ngay_cap': '2025-01-01',  # Giá trị mặc định tránh lỗi NOT NULL
                'noi_cap': 'Chưa cập nhật',
                'cccd': f'CCCD_{ma_cb}',
            },
        )

        # 3. Xử lý Nhóm Hợp đồng
        ten_nhom = (
            str(row['Nhóm HĐ']).strip() if pd.notna(row['Nhóm HĐ']) else 'Mặc định'
        )
        nhom_hd, _ = NhomHD.objects.get_or_create(
            ten_nhom=ten_nhom, defaults={'mo_ta': f'Nhóm {ten_nhom}'}
        )

        # 4. Xử lý Hợp đồng
        so_hop_dong = (
            str(row['Số HĐ']).strip() if pd.notna(row['Số HĐ']) else 'HD_CHUACAT'
        )
        ngay_ky = (
            pd.to_datetime(row['Ngày ký']).date()
            if pd.notna(row['Ngày ký'])
            else '2025-01-01'
        )
        hop_dong, _ = HopDong.objects.get_or_create(
            so_hop_dong=so_hop_dong,
            defaults={
                'can_bo': can_bo,
                'nhom_hd': nhom_hd,
                'ngay_ky': ngay_ky,
                'trang_thai': 'dang_thuc_hien',
            },
        )

        # 5. Lưu thông tin Phân công chi tiết
        PhanCongTre.objects.create(
            hop_dong=hop_dong,
            tre=tre,
            chi_dinh_ct=(
                row['Chỉ định CT'] if pd.notna(row['Chỉ định CT']) else ''
            ),
            so_buoi_du_kien=(
                row['Số buổi dự kiến']
                if pd.notna(row['Số buổi dự kiến'])
                else 0
            ),
            dia_diem_ct=(
                row['Địa điểm CT'] if pd.notna(row['Địa điểm CT']) else ''
            ),
            hinh_thuc_ct=(
                row['Hình thức CT'] if pd.notna(row['Hình thức CT']) else ''
            ),
            dot_phan_cong=(
                row['Đợt phân công'] if pd.notna(row['Đợt phân công']) else 1
            ),
            ky_phan_cong=(
                row['Kỳ phân công'] if pd.notna(row['Kỳ phân công']) else 1
            ),
            ngay_phan_cong=(
                pd.to_datetime(row['Ngày phân công']).date()
                if pd.notna(row['Ngày phân công'])
                else '2025-01-01'
            ),
            dinh_muc_di_lai=(
                row['Định mức đi lại'] if pd.notna(row['Định mức đi lại']) else 0
            ),
        )

      messages.success(
          request, 'Import file Excel phân công và danh mục thành công!'
      )
      return redirect('danh_sach_hop_dong')

    except Exception as e:
      messages.error(request, f'Lỗi khi import file: {str(e)}')

  return render(request, 'quanly/import_phan_cong.html')

def danh_sach_hop_dong(request):
    ds_hop_dong = HopDong.objects.all()
    return render(request, 'quanly/danh_sach_hop_dong.html', {'ds_hop_dong': ds_hop_dong})