import pandas as pd
import numpy as np
import uuid
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from .models import DonVi, Tre, Tinh, Xa, CanBo, NhomHD, PhanBoChiTieu, PhanCongTre
from .forms import DonViForm, TreForm, CanBoForm, NhomHDForm, PhanBoChiTieuForm
from datetime import date
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from .financial import FinancialConfig
from .decorators import (admin_required, dashboard_required, hopdong_required, readonly_required)

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
@dashboard_required
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
@login_required
def danh_sach_nhom_hd(request):
    ds_nhom = NhomHD.objects.all().order_by('-id')
    return render(request, 'quanly/danh_sach_nhom_hd.html', {'ds_nhom': ds_nhom})

@login_required
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

@login_required
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

@login_required
def xoa_nhom_hd(request, id):
    nhom = get_object_or_404(NhomHD, pk=id)
    ten = nhom.ten_nhom_hd
    nhom.delete()
    messages.success(request, f'Đã xóa Nhóm hợp đồng {ten} khỏi hệ thống.')
    return redirect('danh_sach_nhom_hd')

# QUẢN LÝ ĐƠN VỊ
# ================================
@login_required
def danh_sach_don_vi(request):
    ds_don_vi = DonVi.objects.all().order_by('-id')
    return render(request, 'quanly/danh_sach_don_vi.html', {'ds_don_vi': ds_don_vi})

@login_required
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

@login_required
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

@login_required
def xoa_don_vi(request, id):
    don_vi = get_object_or_404(DonVi, pk=id)
    ten = don_vi.ten_don_vi
    don_vi.delete()
    messages.success(request, f'Đã xóa đơn vị {ten} khỏi hệ thống.')
    return redirect('danh_sach_don_vi')

# 1. DANH SÁCH TRẺ
@login_required
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
@login_required
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
@login_required
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
@login_required
def xoa_tre(request, id):
    tre = get_object_or_404(Tre, pk=id)
    ten_tre = tre.ho_ten
    tre.delete()
    messages.success(request, f'Đã xóa dữ liệu của {ten_tre} khỏi hệ thống.')
    return redirect('danh_sach_tre')

# 5. IMPORT TRẺ
@admin_required
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
@login_required
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

@login_required
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

@login_required
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

@login_required
def xoa_can_bo(request, id):
    can_bo = get_object_or_404(CanBo, pk=id)
    ten = can_bo.ho_ten
    can_bo.delete()
    messages.success(request, f'Đã xóa dữ liệu cán bộ {ten} khỏi hệ thống.')
    return redirect('danh_sach_can_bo')

@admin_required
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
@admin_required
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
        hop_dong, _ = PhanBoChiTieu.objects.get_or_create(
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

# =========================================================
# QUY TRÌNH HỢP ĐỒNG: PHÂN BỔ -> ĐỀ XUẤT -> CHÍNH THỨC
# =========================================================
@hopdong_required
def phan_bo_chi_tieu(request):
    """
    BƯỚC 1: Cán bộ tạo Phân bổ chỉ tiêu (Lưu và chuyển thẳng sang Đề xuất Hợp đồng)
    """
    if request.method == 'POST':
        form = PhanBoChiTieuForm(request.POST)
        if form.is_valid():
            hop_dong = form.save(commit=False)
            
            # Gán thống nhất trạng thái chữ thường 'de_xuat'
            hop_dong.trang_thai = 'de_xuat'
            
            # Tự động sinh mã tạm nếu chưa có Số HĐ
            if not hop_dong.so_hop_dong:
                hop_dong.so_hop_dong = f"DX_{uuid.uuid4().hex[:6].upper()}"
                
            hop_dong.save()
            messages.success(request, f"Đã lưu và chuyển đề xuất cho cán bộ {hop_dong.can_bo} thành công!")
            return redirect('danh_sach_de_xuat')
        else:
            messages.error(request, "Lưu thất bại! Vui lòng kiểm tra lại thông tin biểu mẫu.")
    else:
        form = PhanBoChiTieuForm()

    return render(request, 'quanly/phan_bo_chi_tieu.html', {'form': form})

@admin_required
def import_phan_bo(request):
  if request.method == 'POST':
    if 'excel_file' in request.FILES:
      excel_file = request.FILES['excel_file']
      try:
        df = pd.read_excel(excel_file)

        # 1. CHUẨN HÓA TIÊU ĐỀ CỘT: Xóa sạch khoảng trắng ẩn, \xa0, xuống dòng
        df.columns = [
            str(col).strip().replace('\xa0', '').replace(' ', '')
            for col in df.columns
        ]

        preview_data = []
        valid_count = 0
        invalid_count = 0

        # Hàm đọc giá trị an toàn từ row
        def get_column_value(row, col_name):
          val = row.get(col_name)
          if pd.isna(val) or val is None:
            return None
          val_str = str(val).strip()
          return val_str if val_str != '' and val_str.lower() != 'nan' else None

        for idx, (_, row) in enumerate(df.iterrows()):
          row_num = idx + 2
          errors = []

          # Bắt lỗi Mã CBCT
          ma_cb = get_column_value(row, 'MaCBCT')
          can_bo = None
          if not ma_cb:
            errors.append('Thiếu mã CBCT')
          else:
            try:
              can_bo = CanBo.objects.get(ma_can_bo=ma_cb)
            except CanBo.DoesNotExist:
              errors.append(f"Không tìm thấy cán bộ mã '{ma_cb}'")

          # Xử lý ThamGiaCt (Có / Không)
          raw_tham_gia = get_column_value(row, 'ThamGiaCt')
          if raw_tham_gia is None:
            tham_gia_ct = True
          else:
            tham_gia_ct = raw_tham_gia.lower() in [
                '1',
                '1.0',
                'có',
                'co',
                'true',
                'x',
                'yes',
            ]

          # BẮT LỖI SỐ BUỔI PHCN
          val_buoi_phcn = get_column_value(row, 'SoBuoiPHCN')
          if val_buoi_phcn is None:
            errors.append('Thiếu số buổi PHCN')
            so_buoi_phcn = 0
          else:
            try:
              so_buoi_phcn = int(float(val_buoi_phcn))
            except (ValueError, TypeError):
              errors.append('Số buổi PHCN không hợp lệ')
              so_buoi_phcn = 0

          # BẮT LỖI SỐ BUỔI CSXH
          val_buoi_cs = get_column_value(row, 'SoBuoiCS')
          if val_buoi_cs is None:
            errors.append('Thiếu số buổi CSXH')
            so_buoi_cs = 0
          else:
            try:
              so_buoi_cs = int(float(val_buoi_cs))
            except (ValueError, TypeError):
              errors.append('Số buổi CSXH không hợp lệ')
              so_buoi_cs = 0

          # Số trẻ PHCN & CSXH
          val_tre_phcn = get_column_value(row, 'SoTrePHCN')
          so_tre_phcn = int(float(val_tre_phcn)) if val_tre_phcn else 0

          val_tre_cs = get_column_value(row, 'SoTreCS')
          so_tre_cs = int(float(val_tre_cs)) if val_tre_cs else 0

          # Định mức đi lại
          dmdl_phcn_code = get_column_value(row, 'DMDL_PHCN') or '1'
          dmdl_cs_code = get_column_value(row, 'DMDL_CS') or '1'

          dmdl_phcn_val = (
              FinancialConfig.DON_GIA_DI_LAI_DM1
              if dmdl_phcn_code in ['1', '1.0']
              else FinancialConfig.DON_GIA_DI_LAI_DM2
          )
          dmdl_cs_val = (
              FinancialConfig.DON_GIA_DI_LAI_DM1
              if dmdl_cs_code in ['1', '1.0']
              else FinancialConfig.DON_GIA_DI_LAI_DM2
          )

          # Tính toán giá trị dự kiến
          cong_phcn = so_tre_phcn * so_buoi_phcn * FinancialConfig.DON_GIA_CONG
          di_lai_phcn = so_tre_phcn * so_buoi_phcn * dmdl_phcn_val

          cong_cs = so_tre_cs * so_buoi_cs * FinancialConfig.DON_GIA_CONG
          di_lai_cs = so_tre_cs * so_buoi_cs * dmdl_cs_val

          gia_tri_du_kien = cong_phcn + di_lai_phcn + cong_cs + di_lai_cs

          is_valid = len(errors) == 0
          if is_valid:
            valid_count += 1
          else:
            invalid_count += 1

          preview_data.append({
              'row_num': row_num,
              'ma_cb': ma_cb or 'N/A',
              'ten_cb': can_bo.ho_ten if can_bo else 'N/A',
              'can_bo_id': can_bo.pk if can_bo else None,
              'nhom_hd': int(float(get_column_value(row, 'NhomHD') or 1)),
              'tham_gia_ct': tham_gia_ct,
              'so_tre_phcn': so_tre_phcn,
              'so_buoi_phcn': so_buoi_phcn,
              'dmdl_phcn_val': dmdl_phcn_val,
              'so_tre_cs': so_tre_cs,
              'so_buoi_cs': so_buoi_cs,
              'dmdl_cs_val': dmdl_cs_val,
              'gia_tri_du_kien': gia_tri_du_kien,
              'is_valid': is_valid,
              'error_msg': '; '.join(errors),
          })

        request.session['import_phan_bo_valid_data'] = [
            item for item in preview_data if item['is_valid']
        ]

        return render(
            request,
            'quanly/import_phan_bo.html',
            {
                'preview_data': preview_data,
                'valid_count': valid_count,
                'invalid_count': invalid_count,
                'has_preview': True,
            },
        )

      except Exception as e:
        messages.error(request, f'Lỗi đọc file Excel: {e}')
        return redirect('import_phan_bo')

    elif 'confirm_save' in request.POST:
      valid_items = request.session.get('import_phan_bo_valid_data', [])
      if not valid_items:
        messages.error(request, 'Không có dữ liệu hợp lệ để lưu!')
        return redirect('import_phan_bo')

      records_to_create = []
      for item in valid_items:
        records_to_create.append(
            PhanBoChiTieu(
                can_bo_id=item['can_bo_id'],
                nhom_hd=item['nhom_hd'],
                tham_gia_ct=item['tham_gia_ct'],
                so_tre_phcn=item['so_tre_phcn'],
                so_buoi_phcn=item['so_buoi_phcn'],
                dinh_muc_di_lai_phcn=item['dmdl_phcn_val'],
                so_tre_cs=item['so_tre_cs'],
                so_buoi_cs=item['so_buoi_cs'],
                dinh_muc_di_lai_cs=item['dmdl_cs_val'],
                gia_tri_hd_du_kien=item['gia_tri_du_kien'],
                trang_thai='DE_XUAT',
            )
        )

      PhanBoChiTieu.objects.bulk_create(records_to_create)
      if 'import_phan_bo_valid_data' in request.session:
        del request.session['import_phan_bo_valid_data']

      messages.success(
          request,
          f'Đã lưu thành công {len(records_to_create)} bản ghi vào Database!',
      )
      return redirect('danh_sach_de_xuat')

  return render(request, 'quanly/import_phan_bo.html', {'has_preview': False})

@admin_required
def sua_phan_bo_chi_tieu(request, pk):
  item = get_object_or_404(PhanBoChiTieu, pk=pk)

  if request.method == 'POST':
    try:
      # Lấy số buổi điều chỉnh từ Form
      so_buoi_phcn = int(request.POST.get('so_buoi_phcn', item.so_buoi_phcn))
      so_buoi_cs = int(request.POST.get('so_buoi_cs', item.so_buoi_cs))

      item.so_buoi_phcn = so_buoi_phcn
      item.so_buoi_cs = so_buoi_cs

      # Tự động tính lại Giá trị hợp đồng dự kiến dựa trên số buổi mới
      cong_phcn = (
          item.so_tre_phcn * item.so_buoi_phcn * FinancialConfig.DON_GIA_CONG
      )
      di_lai_phcn = (
          item.so_tre_phcn * item.so_buoi_phcn * item.dinh_muc_di_lai_phcn
      )

      cong_cs = (
          item.so_tre_cs * item.so_buoi_cs * FinancialConfig.DON_GIA_CONG
      )
      di_lai_cs = item.so_tre_cs * item.so_buoi_cs * item.dinh_muc_di_lai_cs

      item.gia_tri_hd_du_kien = cong_phcn + di_lai_phcn + cong_cs + di_lai_cs
      item.save()

      messages.success(
          request,
          f'Đã cập nhật số buổi & tính lại Giá trị HĐ cho CBCT {item.can_bo.ho_ten}!',
      )
    except Exception as e:
      messages.error(request, f'Lỗi khi cập nhật dữ liệu: {e}')

  return redirect('danh_sach_de_xuat')

@hopdong_required
def danh_sach_phan_bo(request):
    danh_sach = PhanBoChiTieu.objects.select_related('can_bo').all().order_by('-id')
    return render(request, 'quanly/danh_sach_phan_bo.html', {'danh_sach': danh_sach})

@hopdong_required
def danh_sach_de_xuat(request):
    query = request.GET.get('q', '').strip()
    
    ds_de_xuat = PhanBoChiTieu.objects.filter(
        trang_thai__in=['de_xuat', 'DE_XUAT']
    ).order_by('-id')
    
    if query:
        ds_de_xuat = ds_de_xuat.filter(
            Q(so_hop_dong__icontains=query) |
            Q(can_bo__ho_ten__icontains=query) |
            Q(can_bo__ma_can_bo__icontains=query)
        )

    paginator = Paginator(ds_de_xuat, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'danh_sach': page_obj,   # Khớp chính xác với {% for item in danh_sach %} trong HTML
        'page_obj': page_obj,
        'query': query,
    }
    return render(request, 'quanly/danh_sach_de_xuat.html', context)

@hopdong_required
def tao_hop_dong_chinh_thuc(request, pk):
    hop_dong = get_object_or_404(PhanBoChiTieu, pk=pk)

    if request.method == 'POST':
        so_hop_dong_moi = request.POST.get('so_hop_dong')
        ngay_ky = request.POST.get('ngay_ky')
        tu_ngay = request.POST.get('tu_ngay')
        den_ngay = request.POST.get('den_ngay')

        if so_hop_dong_moi:
            hop_dong.so_hop_dong = so_hop_dong_moi
        if ngay_ky:
            hop_dong.ngay_ky = ngay_ky
        if tu_ngay:
            hop_dong.tu_ngay = tu_ngay
        if den_ngay:
            hop_dong.den_ngay = den_ngay
            
        # Gán trạng thái chuẩn là 'chinh_thuc'
        hop_dong.trang_thai = 'chinh_thuc'
        hop_dong.save()

        messages.success(request, f"Đã duyệt thành công! Hợp đồng {hop_dong.so_hop_dong} đã chính thức có hiệu lực.")
        return redirect('danh_sach_hop_dong')

    context = {'hop_dong': hop_dong}
    return render(request, 'quanly/xac_nhan_tao_hop_dong.html', context)

@readonly_required
def danh_sach_hop_dong(request):
    query = request.GET.get('q', '').strip()
    
    # Lấy danh sách các hợp đồng chính thức
    ds_hop_dong = PhanBoChiTieu.objects.exclude(
        trang_thai__in=['de_xuat', 'DE_XUAT']
    ).order_by('-id')
    
    if query:
        ds_hop_dong = ds_hop_dong.filter(
            Q(so_hop_dong__icontains=query) |
            Q(can_bo__ho_ten__icontains=query)
        )

    paginator = Paginator(ds_hop_dong, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'hop_dongs': page_obj,     # <--- Khớp chính xác với {% for hd in hop_dongs %} trong HTML
        'page_obj': page_obj,
        'danh_sach': page_obj,
        'hop_dong_list': page_obj,
        'query': query,
    }
    return render(request, 'quanly/danh_sach_hop_dong.html', context)