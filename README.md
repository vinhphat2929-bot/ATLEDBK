# ATLED BK - Backup Tool

ATLED BK là ứng dụng Windows dùng để theo dõi thư mục backup POS, tự động phát hiện file `.bak`, nén sang `.zip`, upload lên Google Drive, gửi thông báo Telegram, tạo báo cáo cuối ngày và hỗ trợ cập nhật ứng dụng tự động.

## Tổng quan chức năng

- Theo dõi thư mục backup theo thời gian thực bằng `watchdog`
- Tự động phát hiện file `.bak` mới xuất hiện trong thư mục được cấu hình
- Kiểm tra file ổn định trước khi xử lý để tránh nén khi file còn đang được ghi
- Nén file `.bak` thành `.zip` theo tên tiệm và timestamp
- Upload file `.zip` lên Google Drive bằng Service Account
- Tự tạo thư mục tiệm trên Google Drive nếu chưa tồn tại
- Dọn dẹp backup cũ trên Google Drive theo chính sách giữ lại `30` bản gần nhất
- Xóa file `.bak` gốc và file `.zip` tạm ở máy sau khi upload thành công
- Gửi thông báo Telegram cho các luồng backup, system, report và update
- Hỗ trợ lệnh Telegram `/list` và `/check`
- Tự gửi báo cáo cuối ngày vào `2:00 AM`
- Hỗ trợ tự kiểm tra update cho bản `.exe`
- Có giao diện PyQt6, icon khay hệ thống và chạy nền sau khi kích hoạt

## Kiến trúc chính

Ứng dụng tập trung gần như toàn bộ logic trong `main.py`.

### 1. Giao diện cấu hình

Chạy bằng:

```bash
python main.py
```

Hoặc khi đã build:

```bash
ATLED_BK.exe
```

Giao diện gồm 3 bước:

1. Nhập `Merchant Name`
2. Chọn `Backup Directory`
3. Bấm `ENABLE AUTO BACKUP`

Sau khi kích hoạt thành công, app sẽ:

- Lưu cấu hình vào `config.json`
- Khởi tạo kết nối Google Drive
- Bắt đầu thread theo dõi thư mục backup
- Tạo shortcut auto-start trong thư mục Windows Startup nếu đang chạy bằng `.exe`
- Thu nhỏ xuống khay hệ thống khi người dùng bấm `Done` hoặc đóng cửa sổ lúc app đang chạy

## Cấu hình

App dùng 3 nguồn cấu hình theo thứ tự merge:

- `config.json` nằm cạnh file chạy
- `config.json` ở resource path
- `config.json` ở thư mục cha cũ để tương thích bản legacy

Các khóa cấu hình chính:

- `STORE_NAME`: tên tiệm
- `WATCH_DIRECTORY`: thư mục chứa file `.bak`
- `TELEGRAM_TOKEN`: bot thông báo backup chính
- `TELEGRAM_CHAT_ID`: box nhận thông báo backup chính
- `TELEGRAM_SYSTEM_TOKEN`: bot thông báo system
- `TELEGRAM_SYSTEM_CHAT_ID`: box nhận thông báo system
- `TELEGRAM_REPORT_TOKEN`: bot báo cáo cuối ngày và lệnh Telegram
- `TELEGRAM_REPORT_CHAT_ID`: box nhận báo cáo cuối ngày và xử lý `/list`, `/check`
- `TELEGRAM_UPDATE_TOKEN`: bot thông báo update app
- `TELEGRAM_UPDATE_CHAT_ID`: box nhận thông báo update app
- `AUTO_START_ENABLED`: bật auto-start khi mở máy
- `AUTO_UPDATE_ENABLED`: bật tự kiểm tra update
- `LAST_UPDATE_CHECK_DATE`: ngày đã check update gần nhất

## Google Drive

### Cách xác thực

App ưu tiên đọc `credentials.json` nếu file này tồn tại trong thư mục app. Nếu không có, app fallback sang `SERVICE_ACCOUNT_INFO` được nhúng trong `main.py`.

### Quyền cần có

Service Account cần được chia sẻ quyền trên thư mục Google Drive gốc (`PARENT_FOLDER_ID`) để app có thể:

- Tìm thư mục tiệm
- Tạo thư mục tiệm mới
- Upload file backup
- Liệt kê danh sách tiệm để phục vụ `/list`
- Kiểm tra tình trạng backup để phục vụ `/check` và báo cáo cuối ngày

### Luồng backup

Khi một file `.bak` mới xuất hiện:

1. App đợi file ổn định
2. Tạo file `.zip` theo format `STORE_NAME_YYYY-MM-DD_HH-MM-SS.zip`
3. Tìm hoặc tạo thư mục tiệm trên Google Drive
4. Upload file lên Drive
5. Dọn backup cũ, chỉ giữ lại `30` bản gần nhất
6. Xóa file local sau khi hoàn tất
7. Gửi Telegram báo thành công hoặc lỗi

## Telegram

App đang tách riêng 4 nhóm thông báo:

### 1. Backup box

Dùng để gửi:

- backup thành công
- lỗi nén file
- lỗi upload Drive
- lỗi worker khi xử lý background

### 2. System box

Dùng để gửi:

- app bắt đầu monitor
- app tắt
- các thông báo mức hệ thống liên quan tới phiên chạy

### 3. Report box

Dùng để gửi:

- báo cáo cuối ngày
- kết quả lệnh `/list`
- kết quả lệnh `/check`

Lệnh Telegram hiện được hỗ trợ:

- `/list`: liệt kê danh sách merchant folder đã cấu hình trên Google Drive
- `/check`: kiểm tra các tiệm chưa có backup trong khoảng ngày gần đây theo logic của app

### 4. Update box

Dùng để gửi:

- thông báo khi có bản update mới
- trạng thái check/cài update tự động

## Báo cáo cuối ngày

App có thread riêng chạy nền để gửi báo cáo mỗi ngày lúc `2:00 AM` theo giờ máy.

Báo cáo phục vụ theo dõi:

- tổng số folder tiệm đang cấu hình
- số tiệm backup thành công
- số tiệm có vấn đề hoặc thiếu backup

## Auto-start

Khi người dùng kích hoạt backup và app đang chạy dưới dạng `.exe`, ứng dụng sẽ tạo shortcut trong thư mục Windows Startup để lần sau máy mở lên app tự chạy với tham số:

```bash
--background
```

Nếu chạy bằng `python main.py`, app vẫn dùng được nhưng sẽ không tạo auto-start shortcut dành cho người dùng cuối.

## Auto-update

App hỗ trợ kiểm tra update tự động cho bản `.exe`.

Điều kiện để tính năng hoạt động:

- `AUTO_UPDATE_ENABLED = true`
- app đang chạy bằng file `.exe`
- trong ngày hiện tại chưa check update trước đó
- file update mới phải được upload lên Google Drive:
  - **File text** (chứa version, ví dụ: `v1.0.9`) → lấy **File ID** điền vào `UPDATE_VERSION_FILE_ID`
  - **File exe** (đặt version trong tên, ví dụ: `ATLED_BK_v1.0.9.exe`) → lấy **File ID** điền vào `UPDATE_EXE_FILE_ID`

Cơ chế auto-update đầu ngày:

- sau khi app khởi động, thread update chờ khoảng `20` giây rồi mới check
- mỗi ngày chỉ check `1` lần bằng `LAST_UPDATE_CHECK_DATE`
- app đọc version từ file text trên Drive (`UPDATE_VERSION_FILE_ID`)
- app so sánh version bằng semantic versioning (`drive_version > current_version`)
- nếu có bản mới → tải exe từ Drive (`UPDATE_EXE_FILE_ID`) → thay thế và restart
- sau khi check xong, app ghi ngày hiện tại vào `config.json` qua `LAST_UPDATE_CHECK_DATE`

Ngoài kiểm tra tự động, menu khay hệ thống còn có nút `Update` để người dùng chủ động chạy cập nhật.

### Manual update không cần bấm Active lại

Khi người dùng bấm `Update` trong lúc app đang monitoring:

- app tải file mới về
- app thay file `.exe` hiện tại bằng file mới
- app restart lại với tham số `--background`
- app mới tự đọc lại `config.json`
- nếu `STORE_NAME` và `WATCH_DIRECTORY` đã có sẵn, app sẽ tự gọi `_start_monitoring(...)`
- giao diện không bắt người dùng phải bấm `ENABLE AUTO BACKUP` lại

Nếu app không ở trạng thái monitoring nhưng đã có đủ `STORE_NAME` và `WATCH_DIRECTORY`, code hiện tại vẫn có thể chọn restart nền sau update.

## Khay hệ thống

Khi app đang monitor, người dùng có thể:

- đóng cửa sổ để app ẩn xuống tray
- click icon tray để mở lại
- dùng menu tray với các lựa chọn `Open`, `Update`, `Exit`

## Log

Log được ghi vào:

```text
logs/backup.log
```

Các nhóm log chính gồm:

- khởi tạo Drive
- theo dõi thư mục
- nén file
- upload file
- Telegram
- daily report
- auto-update
- lỗi runtime

## Chạy ứng dụng

### Chạy trong môi trường Python

```bash
python main.py
```

### Chạy ẩn nền sau khi đã build `.exe`

App có thể được gọi với tham số nội bộ như:

```bash
ATLED_BK.exe --background
```

Ngoài ra app còn có tham số nội bộ phục vụ sau update:

```bash
ATLED_BK.exe --auto-updated
```

## Những điểm README cũ chưa đúng và đã được cập nhật

README cũ mô tả chưa đúng ở các điểm sau:

- mô tả app chạy theo `Task Scheduler` lúc `23:00`, trong khi app thực tế theo dõi thư mục theo thời gian thực bằng `watchdog`
- giao diện thực tế có `3 bước`, không phải `2 bước`
- app hiện có `system tray`, `auto-start`, `auto-update`, Telegram commands và daily report nhưng README cũ chưa nói rõ
- cấu hình Telegram hiện chia nhiều box/bot theo chức năng, không còn là một bot duy nhất
- app ghi log vào `logs/backup.log` đúng, nhưng luồng vận hành hiện phong phú hơn nhiều so với mô tả cũ

## Ghi chú vận hành

- Tên merchant nên nhập đúng theo chuẩn nội bộ để đồng bộ với thư mục Google Drive
- Thư mục backup phải tồn tại trước khi kích hoạt
- Nếu Google Drive hoặc Telegram bị lỗi mạng, app có cơ chế retry nhiều lần
- Nếu thiếu quyền vào `PARENT_FOLDER_ID`, upload và các lệnh `/list`, `/check` sẽ không hoạt động đúng
