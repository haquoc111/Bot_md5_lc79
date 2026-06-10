# 🤖 SXD Prediction Bot – Hướng dẫn deploy lên Render

## 📁 Cấu trúc thư mục
```
telegram_bot/
├── bot.py           # Logic chính của bot
├── server.py        # Web server (giữ instance sống trên Render)
├── requirements.txt # Thư viện Python
├── render.yaml      # Cấu hình tự động cho Render
├── Procfile         # Lệnh khởi động
├── qr_payment.png   # ⚠️ Bạn cần tự thêm file ảnh QR vào đây
└── data/            # Tự tạo khi chạy (lưu key, user, pending)
```

---

## 🚀 Các bước deploy lên Render

### Bước 1 – Thêm ảnh QR
Đặt ảnh QR chuyển khoản của bạn vào thư mục với tên: `qr_payment.png`

### Bước 2 – Upload lên GitHub
1. Tạo một repo mới trên GitHub (private hoặc public)
2. Upload toàn bộ thư mục `telegram_bot/` lên repo đó

### Bước 3 – Tạo Web Service trên Render
1. Vào https://render.com và đăng nhập
2. Nhấn **New → Web Service**
3. Kết nối với GitHub repo vừa tạo
4. Điền thông tin:
   - **Name:** `sxd-prediction-bot`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python server.py`
   - **Instance Type:** Free
5. Nhấn **Create Web Service**

### Bước 4 – Thêm Disk (lưu dữ liệu key)
1. Vào tab **Disks** trong Web Service
2. Nhấn **Add Disk**
   - Mount Path: `/opt/render/project/src/data`
   - Size: 1 GB
3. Lưu lại

---

## 🎮 Lệnh Admin (Telegram ID: 7680266707)

| Lệnh | Mô tả |
|------|-------|
| `/confirm_<user_id>_<pkg>` | Xác nhận thanh toán, tạo key tự động |
| `/reject_<user_id>` | Từ chối thanh toán |
| `/listkeys` | Xem danh sách tất cả key |
| `/delkey <KEY>` | Xóa một key |
| `/broadcast <nội dung>` | Gửi thông báo đến tất cả user |

### Ví dụ tạo key:
Khi user gửi bill, bot sẽ forward đến admin kèm lệnh:
```
/confirm_123456789_1ngay
/confirm_123456789_1tuan
/confirm_123456789_1nam
/confirm_123456789_vinhvien
/confirm_123456789_5h
```

---

## 📦 Các gói Key

| Mã gói | Tên hiển thị | Giá | Thời gian |
|--------|-------------|-----|-----------|
| `5h` | 5 Giờ ⚡ | 10.000đ | 5 giờ |
| `1ngay` | 1 Ngày | 20.000đ | 24 giờ |
| `1tuan` | 1 Tuần | 50.000đ | 7 ngày |
| `1nam` | 1 Năm 🔥SALE | 99.000đ | 365 ngày |
| `vinhvien` | Vĩnh Viễn ♾️ | 150.000đ | Không giới hạn |

---

## ⚙️ Tính năng dự đoán

### Dự đoán bằng API
- Lấy dữ liệu thời gian thực từ API gốc
- Phân tích cầu thông minh (theo cầu / bẻ cầu)
- Hiển thị: Phiên, kết quả, xúc xắc, phiên mới, dự đoán, độ tin cậy

### Dự đoán bằng MD5
- Người dùng nhập mã MD5 (32 ký tự hex)
- Phân tích entropy, parity, weighted segments
- Không dự đoán ngẫu nhiên – mỗi mã MD5 cho kết quả xác định

---

## 🔒 Bảo mật Key
- Mỗi Key chỉ dùng được cho **1 tài khoản Telegram duy nhất**
- Khi hết hạn, không thể dùng tính năng dự đoán
- Admin có thể xoá key bất kỳ lúc nào

---

## ❓ Hỗ trợ
Liên hệ: @cskh09099
