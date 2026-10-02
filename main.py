import sqlite3
import re

DATABASE_NAME = 'cellphones_data.db'

# =========================================================
# HELPER: KẾT NỐI DATABASE
# =========================================================
def connect_db():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# =========================================================
# HELPER: IN BẢNG (Giữ nguyên nền tảng cũ)
# =========================================================
def print_table(cursor):
    rows = cursor.fetchall()
    if not rows:
        print("-> [HỆ THỐNG] Không tìm thấy dữ liệu phù hợp.")
        return

    col_names = [description[0] for description in cursor.description]
    col_widths = [max(len(str(name)), 12) for name in col_names]

    for row in rows:
        for i, value in enumerate(row):
            text = "N/A" if value is None else str(value)
            if len(text) > 50: text = text[:47] + "..."
            col_widths[i] = max(col_widths[i], len(text))

    header = " | ".join(f"{name:<{col_widths[i]}}" for i, name in enumerate(col_names))
    print("-" * len(header))
    print(header)
    print("-" * len(header))

    for row in rows:
        values = []
        for i, value in enumerate(row):
            text = "N/A" if value is None else str(value)
            if len(text) > 50: text = text[:47] + "..."
            values.append(f"{text:<{col_widths[i]}}")
        print(" | ".join(values))
    print("-" * len(header))
    print()

# =========================================================
# BƯỚC 1 & 2: EXTRACT & TRANSFORM & LOAD (ETL)
# (Chạy 1 lần duy nhất để làm sạch rác, tạo Database chuẩn)
# =========================================================
def chuan_hoa_du_lieu_ETL():
    print("[HỆ THỐNG] Đang chạy tiến trình ETL làm sạch dữ liệu...")
    conn = connect_db()
    cursor = conn.cursor()

    # 1. Tạo bảng chuẩn (Data Warehouse)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS laptops_clean (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ten_san_pham TEXT,
            gia_ban INTEGER,
            gia_goc INTEGER,
            gia_sinh_vien INTEGER,
            ram_gb INTEGER,
            kha_nang_nang_cap TEXT,
            gpu_tier INTEGER,
            battery_wh INTEGER,
            is_gaming_screen BOOLEAN,
            is_design_screen BOOLEAN,
            is_office_screen BOOLEAN,
            has_office BOOLEAN,
            has_warranty BOOLEAN
        )
    """)
    cursor.execute("DELETE FROM laptops_clean") # Reset data cũ

    # 2. Đọc dữ liệu thô từ bảng cũ
    try:
        cursor.execute("SELECT * FROM laptops")
        raw_rows = cursor.fetchall()
    except sqlite3.OperationalError:
        print("[LỖI] Không tìm thấy bảng 'laptops' chứa dữ liệu gốc.")
        conn.close()
        return

    # 3. Transform (Làm sạch) & Load (Đưa vào bảng mới)
    for row in raw_rows:
        ten = row['Ten_San_Pham']
        
        # Xử lý Giá
        def get_price(val):
            if not val or val == 'N/A': return 0
            digits = re.sub(r'\D', '', str(val))
            return int(digits) if digits else 0
            
        gia_ban = get_price(row['Gia_Ban'])
        gia_goc = get_price(row['Gia_Goc'])
        gia_sv = get_price(row['Gia_Sinh_Vien'])
        
        # Xử lý RAM
        ram_str = str(row['RAM']).upper()
        ram_match = re.search(r'(\d+)\s*GB', ram_str)
        ram_gb = int(ram_match.group(1)) if ram_match else 0
        
        kha_nang_nang_cap = "Không"
        if "KHE" in ram_str: kha_nang_nang_cap = "Có"

        # Xử lý GPU
        gpu_str = str(row['Card_Do_Hoa']).upper()
        gpu_tier = 1 # Onboard
        if any(x in gpu_str for x in ['RTX 50', 'RTX 4080', 'RTX 4090']): gpu_tier = 4
        elif any(x in gpu_str for x in ['RTX', 'RX 7', 'RX 8']): gpu_tier = 3
        elif any(x in gpu_str for x in ['GTX', 'MX', 'ARC', 'RADEON']): gpu_tier = 2
        
        # Xử lý Pin
        pin_str = str(row['Pin_Va_Nguon']).upper()
        pin_match = re.search(r'(\d+)\s*WH', pin_str)
        battery_wh = int(pin_match.group(1)) if pin_match else 0
        
        # Xử lý Màn hình (Gán cờ Boolean để SQL query siêu tốc)
        mh_str = str(row['Man_Hinh']).upper()
        is_gaming = 1 if re.search(r'(120|144|165|180|240|360)HZ', mh_str) else 0
        is_design = 1 if re.search(r'(OLED|SRGB|DCI-P3)', mh_str) else 0
        is_office = 1 if re.search(r'(ANTI-GLARE|CHỐNG CHÓI|VIỀN MỎNG|16:10)', mh_str) else 0
        
        # Xử lý Bảo hành & Phần mềm
        mo_ta = str(row['Mo_Ta']).upper()
        cam_ket = str(row['Cam_Ket_San_Pham']).upper()
        has_office = 1 if 'OFFICE' in mo_ta else 0
        has_warranty = 1 if 'BẢO HÀNH' in mo_ta or 'BẢO HÀNH' in cam_ket else 0

        # Insert vào Database sạch
        cursor.execute("""
            INSERT INTO laptops_clean (
                ten_san_pham, gia_ban, gia_goc, gia_sinh_vien, ram_gb, kha_nang_nang_cap,
                gpu_tier, battery_wh, is_gaming_screen, is_design_screen, is_office_screen,
                has_office, has_warranty
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ten, gia_ban, gia_goc, gia_sv, ram_gb, kha_nang_nang_cap, gpu_tier, 
              battery_wh, is_gaming, is_design, is_office, has_office, has_warranty))

    # 4. Tối ưu hóa Database (Tạo Index)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ram ON laptops_clean(ram_gb)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpu ON laptops_clean(gpu_tier)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gia ON laptops_clean(gia_ban)")
    
    conn.commit()
    conn.close()
    print("[HỆ THỐNG] ETL Hoàn tất. Sẵn sàng phục vụ!")

# =========================================================
# BƯỚC 3: EXTRACT (CÁC CHỨC NĂNG TRUY VẤN SIÊU TỐC)
# =========================================================

def so_sanh_hieu_nang_da_nhiem_bo_nho():
    print("\n[1] SO SÁNH RAM & KHẢ NĂNG NÂNG CẤP")
    conn = connect_db()
    cursor = conn.cursor()
    # SQL giờ đây ngắn gọn, không dùng hàm xử lý chuỗi
    cursor.execute("""
        SELECT 
            ten_san_pham AS "Tên Sản Phẩm",
            ram_gb || ' GB' AS "Dung Lượng RAM",
            kha_nang_nang_cap AS "Khả Năng Nâng Cấp"
        FROM laptops_clean
        WHERE ram_gb > 0
        ORDER BY ram_gb DESC
        LIMIT 10
    """)
    print_table(cursor)
    conn.close()

def loc_kha_nang_xu_ly_do_hoa():
    print("\n[2] LỌC KHẢ NĂNG XỬ LÝ ĐỒ HỌA")
    print("1 - Văn phòng\n2 - Thiết kế cơ bản\n3 - Game trung - cao\n4 - Game AAA / đồ họa nặng")
    try:
        cap_do = int(input("-> Chọn cấp độ (1-4): ").strip())
        if cap_do not in [1, 2, 3, 4]: raise ValueError
    except ValueError:
        print("-> Vui lòng nhập số từ 1 đến 4."); return

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            ten_san_pham AS "Tên Sản Phẩm",
            gia_ban AS "Giá Bán (VNĐ)",
            'Cấp ' || gpu_tier AS "Phân Cấp GPU",
            CASE 
                WHEN gpu_tier > ? THEN 'Dư sức đáp ứng'
                WHEN gpu_tier = ? THEN 'Vừa đủ nhu cầu'
            END AS "Đánh Giá"
        FROM laptops_clean
        WHERE gpu_tier >= ? AND gia_ban > 0
        ORDER BY gpu_tier DESC
        LIMIT 8
    """, (cap_do, cap_do, cap_do))
    print_table(cursor)
    conn.close()

def tinh_toan_thoi_luong_su_dung_pin():
    print("\n[3] SO SÁNH DUNG LƯỢNG PIN")
    kieu_dung = input("-> Cần ưu tiên pin lớn để dùng lâu? (Y/N): ").strip().upper()
    conn = connect_db()
    cursor = conn.cursor()
    
    sql = """
        SELECT 
            ten_san_pham AS "Tên Sản Phẩm",
            battery_wh || ' Wh' AS "Dung Lượng Pin",
            CASE 
                WHEN battery_wh >= 80 THEN 'Rất trâu bò'
                WHEN battery_wh >= 60 THEN 'Khá tốt'
                WHEN battery_wh >= 45 THEN 'Trung bình'
                ELSE 'Dung lượng thấp'
            END AS "Phân Loại"
        FROM laptops_clean
        WHERE battery_wh > 0
    """
    if kieu_dung == 'Y': sql += " AND battery_wh >= 60"
    sql += " ORDER BY battery_wh DESC LIMIT 5"
    
    cursor.execute(sql)
    print_table(cursor)
    conn.close()

def goi_y_chuong_trinh_uu_dai_thanh_toan():
    print("\n[4] SO SÁNH KỊCH BẢN TIẾT KIỆM ")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            ten_san_pham AS "Tên Sản Phẩm",
            CASE WHEN gia_goc > 0 THEN gia_goc ELSE gia_ban END AS "Giá Cũ",gia_sinh_vien AS "Giá Học Sinh - Sinh Viên",
            (CASE WHEN gia_goc > 0 THEN gia_goc ELSE gia_ban END) - gia_sinh_vien AS "Tiết Kiệm Được"
        FROM laptops_clean
        WHERE gia_sinh_vien > 0
        ORDER BY "Tiết Kiệm Được" DESC
        LIMIT 5
       
    """)
    print_table(cursor)
    conn.close()

def loc_chinh_sach_bao_hanh_hau_mai():
    print("\n[5] TRA CỨU BẢO HÀNH & PHẦN MỀM ĐI KÈM")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            ten_san_pham AS "Tên Sản Phẩm",
            CASE WHEN has_warranty = 1 THEN 'Có cam kết bảo hành' ELSE 'Chưa rõ' END AS "Bảo Hành",
            CASE WHEN has_office = 1 THEN 'Tặng kèm bản quyền' ELSE 'Không có sẵn' END AS "Office"
        FROM laptops_clean
        WHERE gia_ban > 0
        ORDER BY ten_san_pham
        LIMIT 10
    """)
    print_table(cursor)
    conn.close()

def tu_van_thiet_bi_theo_vong_doi():
    print("\n[6] TƯ VẤN THEO NGÂN SÁCH & THỜI GIAN SỬ DỤNG")
    try:
        budget = int(input("-> Ngân sách tối đa (VNĐ) [Enter = 25000000]: ") or 25000000)
        nam = int(input("-> Dự định dùng bao nhiêu năm? [Enter = 4]: ") or 4)
    except ValueError:
        print("-> Vui lòng nhập số hợp lệ."); return

    conn = connect_db()
    cursor = conn.cursor()
    
    sql = """
        SELECT 
            ten_san_pham AS "Tên Sản Phẩm",
            gia_ban AS "Giá Bán",
            ram_gb || ' GB' AS "Dung Lượng RAM",
            'Cấp ' || gpu_tier AS "Sức Mạnh GPU"
        FROM laptops_clean
        WHERE gia_ban > 0 AND gia_ban <= ?
    """
    if nam >= 5: sql += " AND ram_gb >= 16"
    elif nam >= 3: sql += " AND ram_gb >= 8"

    # Sắp xếp ưu tiên GPU mạnh nhất trong tầm giá, sau đó đến RAM
    sql += " ORDER BY gpu_tier DESC, ram_gb DESC LIMIT 5"
    
    cursor.execute(sql, (budget,))
    print_table(cursor)
    conn.close()

def so_sanh_thong_so_man_hinh_hien_thi():
    print("\n[7] SO SÁNH MÀN HÌNH")
    print("1 - Văn phòng (Bảo vệ mắt, viền mỏng)")
    print("2 - Thiết kế (Màu chuẩn, OLED)")
    print("3 - Gaming (Tần số quét cao)")
    nhu_cau = input("-> Chọn nhu cầu (1-3): ").strip()
    if nhu_cau not in ['1', '2', '3']:
        print("-> Vui lòng chọn 1, 2 hoặc 3."); return

    conn = connect_db()
    cursor = conn.cursor()
    
    sql = "SELECT ten_san_pham AS 'Tên Sản Phẩm', gia_ban AS 'Giá Bán' FROM laptops_clean WHERE gia_ban > 0 "
    
    if nhu_cau == '1': sql += " AND is_office_screen = 1"
    elif nhu_cau == '2': sql += " AND is_design_screen = 1"
    elif nhu_cau == '3': sql += " AND is_gaming_screen = 1"
    
    sql += " LIMIT 5"
    
    cursor.execute(sql)
    print_table(cursor)
    conn.close()

# =========================================================
# MAIN MENU (Không đổi so với bản gốc)
# =========================================================
if __name__ == "__main__":
    chuan_hoa_du_lieu_ETL() # Chạy 1 lần duy nhất khi bật tool

    while True:
        print("\n" + "=" * 65)
        print("              TƯ VẤN LAPTOP")
        print("=" * 65)
        print("1. So sánh RAM & khả năng nâng cấp")
        print("2. Lọc theo khả năng đồ họa")
        print("3. So sánh dung lượng pin")
        print("4. So sánh kịch bản tiết kiệm")
        print("5. Tra cứu bảo hành & phần mềm")
        print("6. Tư vấn theo ngân sách & thời gian sử dụng")
        print("7. So sánh màn hình")
        print("0. Thoát")
        print("=" * 65)

        c = input("Khởi chạy chức năng (0-7): ").strip()

        if c == '1': so_sanh_hieu_nang_da_nhiem_bo_nho()
        elif c == '2': loc_kha_nang_xu_ly_do_hoa()
        elif c == '3': tinh_toan_thoi_luong_su_dung_pin()
        elif c == '4': goi_y_chuong_trinh_uu_dai_thanh_toan()
        elif c == '5': loc_chinh_sach_bao_hanh_hau_mai()
        elif c == '6': tu_van_thiet_bi_theo_vong_doi()
        elif c == '7': so_sanh_thong_so_man_hinh_hien_thi()
        elif c == '0':
            print("\nĐã đóng hệ thống. Tạm biệt!")
            break
        else:
            print("-> Lỗi: Chức năng không tồn tại.")