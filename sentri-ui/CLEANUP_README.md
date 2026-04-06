# Sentri Data Cleanup Scripts

Các script để xóa toàn bộ dữ liệu trong hệ thống Sentri (trừ users và cameras).

## 📁 Files

### 1. `clear_data.py` - Interactive Cleanup (Recommended)

Script tương tác với xác nhận và hiển thị thông tin chi tiết.

**Features:**

- Hiển thị số lượng records hiện tại
- Yêu cầu xác nhận trước khi xóa
- Báo cáo chi tiết kết quả
- Transaction rollback nếu có lỗi
- Xóa cả file vật lý và database

**Usage:**

```bash
python clear_data.py
```

### 2. `quick_clear_data.py` - Quick Cleanup

Script nhanh cho automation hoặc khi chắc chắn muốn xóa.

**Usage:**

```bash
# Hiển thị thông báo cảnh báo
python quick_clear_data.py

# Xóa ngay lập tức (không xác nhận)
python quick_clear_data.py --force
```

### 3. `cleanup.bat` - Windows Batch Script

Script Windows với menu lựa chọn.

**Usage:**

```cmd
cleanup.bat
```

## 🗑️ Dữ liệu sẽ bị xóa

- **Physical Files:**

  - Tất cả frame images trong `static/recordings/frames/`
  - Các file media khác (.jpg, .png, .mp4, etc.)

- **Database Tables:**
  - `notifications` - Thông báo
  - `event_logs` - Lịch sử events
  - `scene_graphs` - Dữ liệu scene graph
  - `media` - Records file media
  - `events` - Định nghĩa loại events

## 💾 Dữ liệu được bảo tồn

- `users` - Tài khoản người dùng
- `auth_users` - Thông tin authentication
- `cameras` - Cấu hình cameras

## ⚠️ Lưu ý quan trọng

1. **Backup trước khi chạy** - Các script này không thể undo!

2. **Chạy từ project root** - Phải chạy từ thư mục chứa `app.py`

3. **Stop server trước** - Tắt Sentri server trước khi chạy cleanup

4. **Check database** - Script tự động kiểm tra và rollback nếu có lỗi

## 🚀 Quy trình khuyến nghị

```bash
# 1. Stop Sentri server
# Ctrl+C trong terminal chạy app.py

# 2. Backup database (optional)
cp sentri.db sentri_backup.db

# 3. Run cleanup
python clear_data.py

# 4. Restart server
python app.py
```

## 🔧 Troubleshooting

**"Database file not found"**

- Đảm bảo chạy từ thư mục chứa `sentri.db`
- Kiểm tra đường dẫn database

**"Permission denied" trên Windows**

- Chạy Command Prompt as Administrator
- Đảm bảo không có process nào đang sử dụng database

**Transaction rollback**

- Script tự động rollback nếu có lỗi
- Database sẽ không bị hỏng
- Check log để xem lỗi cụ thể

## 📊 Example Output

```
🧹 SENTRI DATA CLEANUP SCRIPT
============================================================

📊 Current database status:
------------------------------
notifications   :    45 records 🗑️  TO DELETE
event_logs      :   123 records 🗑️  TO DELETE
scene_graphs    :   234 records 🗑️  TO DELETE
media          :   234 records 🗑️  TO DELETE
events         :     5 records 🗑️  TO DELETE

users          :     2 records ✅ WILL KEEP
cameras        :     3 records ✅ WILL KEEP

⚠️  WARNING: This will permanently delete:
   • All media files and frame images
   • All scene graph data
   • All event logs and notifications
   • All event type definitions

💾 The following will be preserved:
   • User accounts and authentication
   • Camera configurations

🤔 Do you want to proceed? Type 'DELETE' to confirm: DELETE

🚀 Starting cleanup process...
📁 Clearing physical media files...
🗑️  Deleted 234 media files

💾 Clearing database tables...
🗑️  Deleted 45 notifications
🗑️  Deleted 123 event logs
🗑️  Deleted 234 scene graphs
🗑️  Deleted 234 media records
🗑️  Deleted 5 event definitions
✅ Database cleanup completed successfully!
🔄 Auto-increment counters reset

============================================================
✅ CLEANUP COMPLETED SUCCESSFULLY!
============================================================
📊 Summary of deleted data:
   • Physical files    :    234
   • notifications     :     45
   • event_logs        :    123
   • scene_graphs      :    234
   • media            :    234
   • events           :      5
   • Total DB records  :    641

💾 Preserved data:
   • Users             :      2
   • Cameras           :      3

🎉 Your Sentri system is now clean and ready for fresh data!
```
