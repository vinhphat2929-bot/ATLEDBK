# Thuyết trình ứng dụng ATLED BK

## 1. Giới thiệu ngắn gọn

ATLED BK là ứng dụng desktop chạy trên Windows, được xây dựng để tự động hóa việc sao lưu dữ liệu từ hệ thống POS của tiệm. Ứng dụng theo dõi thư mục chứa file backup `.bak`, phát hiện file mới, nén thành `.zip`, tải lên Google Drive, gửi thông báo Telegram và tạo báo cáo cuối ngày.

Nói ngắn gọn, đây là công cụ giúp giảm thao tác thủ công, hạn chế quên backup và tăng khả năng giám sát tập trung cho nhiều tiệm.

---

## 2. Mục tiêu của ứng dụng

Ứng dụng được xây dựng để giải quyết các vấn đề sau:

- Nhân sự không cần tự tay upload file backup mỗi ngày
- Hạn chế rủi ro mất dữ liệu do quên sao lưu
- Có nơi lưu trữ tập trung trên Google Drive
- Có kênh thông báo để biết backup thành công hay thất bại
- Có báo cáo cuối ngày để kiểm tra tình trạng backup của toàn bộ tiệm
- Có cơ chế update app để giảm công cài bản mới thủ công

---

## 3. Ứng dụng dùng công cụ và công nghệ gì

### 3.1. Ngôn ngữ lập trình

- `Python`

Python được dùng để xử lý toàn bộ logic nghiệp vụ của ứng dụng.

### 3.2. Giao diện người dùng

- `PyQt6`

PyQt6 được dùng để tạo cửa sổ cấu hình desktop, nút bấm, nhập liệu, trạng thái hoạt động và icon ở khay hệ thống.

### 3.3. Theo dõi file theo thời gian thực

- `watchdog`

Thư viện này giúp ứng dụng theo dõi thư mục backup và phát hiện ngay khi có file `.bak` mới được tạo.

### 3.4. Nén file

- `zipfile` của Python

Dùng để nén file `.bak` thành `.zip` trước khi tải lên Google Drive.

### 3.5. Kết nối Google Drive

- `google-api-python-client`
- `google.oauth2.service_account`
- `google_auth_httplib2`
- `httplib2`

Các thư viện này dùng để xác thực bằng Service Account và thao tác với Google Drive như tìm thư mục, tạo thư mục, upload file, liệt kê dữ liệu và kiểm tra backup.

### 3.6. Gửi thông báo Telegram

- `requests`
- Telegram Bot API

Ứng dụng dùng Telegram Bot API để gửi tin nhắn đến các nhóm Telegram khác nhau theo từng mục đích: backup, system, report, update.

### 3.7. Chạy nền và xử lý đa luồng

- `threading`
- `QThread`
- `queue`

Các thành phần này giúp app vận hành nhiều tác vụ song song như:

- theo dõi thư mục
- nghe lệnh Telegram
- gửi báo cáo cuối ngày
- tự kiểm tra update
- giữ cho giao diện không bị treo

### 3.8. Tự khởi động cùng Windows

- Windows Startup Shortcut
- PowerShell

Ứng dụng tự tạo shortcut trong thư mục Startup của Windows để lần sau mở máy, app tự chạy lại.

---

## 4. App giải quyết bài toán gì

Nếu không có app này, quy trình backup thường gặp các vấn đề:

- backup được tạo ra nhưng không ai kiểm tra
- file backup nằm trên máy local, dễ mất nếu máy lỗi
- phải vào từng máy để upload thủ công
- khó biết tiệm nào đã backup, tiệm nào chưa
- khó triển khai update hàng loạt

ATLED BK xử lý các bài toán đó bằng cách:

- tự phát hiện file backup mới
- tự nén và đưa lên cloud
- tự thông báo kết quả
- tổng hợp báo cáo cuối ngày
- cho phép kiểm tra nhanh bằng lệnh Telegram
- có thể tự update khi có bản mới

---

## 5. Luồng hoạt động tổng thể

### Bước 1: Người dùng cấu hình lần đầu

Người dùng mở app, nhập:

- tên merchant
- thư mục chứa file `.bak`

Sau đó bấm `ENABLE AUTO BACKUP`.

### Bước 2: App lưu cấu hình

App lưu thông tin vào `config.json` để lần mở sau không cần nhập lại từ đầu.

### Bước 3: App bắt đầu theo dõi thư mục

App chạy một tiến trình theo dõi thư mục backup theo thời gian thực.

### Bước 4: Khi có file `.bak` mới

App sẽ:

1. kiểm tra file đã ghi xong chưa
2. nén file thành `.zip`
3. tìm đúng thư mục của tiệm trên Google Drive
4. nếu chưa có thì tạo mới
5. upload file lên Google Drive
6. xóa file local sau khi hoàn tất
7. gửi thông báo Telegram

### Bước 5: Vận hành dài hạn

Song song với việc theo dõi backup, app còn:

- gửi báo cáo cuối ngày
- nghe lệnh Telegram `/list` và `/check`
- kiểm tra bản update mới
- gửi thông báo system khi app bật hoặc tắt

---

## 6. Các chức năng chính của ứng dụng

### 6.1. Theo dõi thư mục backup tự động

Đây là chức năng cốt lõi.

App không cần người dùng bấm chạy mỗi lần có backup mới. Chỉ cần cấu hình xong, app sẽ luôn theo dõi thư mục đã chọn.

### 6.2. Tự động nén file

Khi phát hiện file `.bak`, app nén thành `.zip` để:

- giảm dung lượng
- dễ upload
- dễ lưu trữ
- thống nhất định dạng

Tên file nén có chứa tên merchant và timestamp, giúp dễ truy vết.

### 6.3. Upload Google Drive

App sẽ upload backup lên thư mục Drive dùng chung.

Nếu thư mục theo tên tiệm chưa có, app sẽ tự tạo. Điều này giúp mở rộng cho nhiều merchant mà không phải tạo tay từng folder.

### 6.4. Dọn backup cũ

App chỉ giữ lại số lượng backup gần nhất trên Google Drive theo chính sách retention. Hiện tại app giữ `30` bản gần nhất cho mỗi tiệm.

Mục tiêu là:

- tránh đầy dữ liệu không cần thiết
- vẫn giữ đủ lịch sử gần nhất để truy xuất khi cần

### 6.5. Gửi thông báo Telegram

App đang chia thông báo thành nhiều luồng riêng để dễ quản lý.

#### a. Backup box

Dùng để báo:

- backup thành công
- lỗi nén file
- lỗi upload Drive
- lỗi xử lý nền

#### b. System box

Dùng để báo:

- app bắt đầu chạy monitor
- app tắt
- các trạng thái hệ thống cần theo dõi

#### c. Report box

Dùng để:

- nhận báo cáo cuối ngày
- xử lý lệnh `/list`
- xử lý lệnh `/check`

#### d. Update box

Dùng để:

- thông báo khi có bản update mới
- thông báo trạng thái cập nhật ứng dụng

### 6.6. Lệnh Telegram điều hành

App hỗ trợ ít nhất 2 lệnh:

- `/list`: liệt kê danh sách merchant folder đang có trên Drive theo logic app
- `/check`: kiểm tra các tiệm chưa có backup hợp lệ trong khoảng cần theo dõi

Điểm hay là người quản lý không cần remote vào máy vẫn có thể kiểm tra trạng thái từ Telegram.

### 6.7. Báo cáo cuối ngày

Mỗi ngày vào `2:00 AM`, app tạo và gửi báo cáo tổng hợp backup.

Báo cáo giúp biết nhanh:

- tổng số tiệm đang theo dõi
- bao nhiêu tiệm đã backup
- bao nhiêu tiệm đang lỗi hoặc chưa có backup

### 6.8. Tự khởi động cùng Windows

Khi app chạy bằng `.exe`, sau khi kích hoạt thành công, app có thể tự đăng ký để mở cùng Windows.

Điều này giúp:

- không cần mở tay mỗi lần bật máy
- giảm rủi ro quên chạy app
- phù hợp môi trường vận hành thực tế tại tiệm

### 6.9. Tự cập nhật ứng dụng

App có cơ chế kiểm tra update cho bản `.exe`.

Mỗi ngày app có thể kiểm tra xem trên Google Drive có bản mới không. Nếu có, app tải file update và có thể kích hoạt quá trình cài đặt.

Điều này giúp:

- giảm thao tác update thủ công
- dễ đồng bộ phiên bản giữa nhiều máy
- hạn chế sai khác phiên bản vận hành

### 6.10. Khay hệ thống

Khi app đang chạy, người dùng không nhất thiết phải để cửa sổ mở. App có thể thu xuống system tray và tiếp tục hoạt động nền.

Menu tray hỗ trợ:

- mở lại app
- update
- thoát app

---

## 7. Thành phần cấu hình quan trọng

### 7.1. Merchant Name

Đây là tên tiệm. Tên này rất quan trọng vì app dùng nó để tạo hoặc tìm folder đúng trên Google Drive.

### 7.2. Watch Directory

Đây là thư mục mà POS hoặc hệ thống backup đang tạo file `.bak`.

Nếu chọn sai thư mục, app sẽ không thấy backup để xử lý.

### 7.3. Google Drive Root Folder

App cần biết thư mục Drive gốc để lưu dữ liệu của tất cả tiệm.

### 7.4. Service Account

App dùng Service Account để xác thực với Google Drive.

Điều này có nghĩa là app không cần đăng nhập Google thủ công trên từng máy người dùng.

### 7.5. Các bot Telegram

App đang tách bot hoặc ít nhất tách cấu hình theo nhiều nhóm chức năng khác nhau. Việc này giúp:

- không lẫn thông báo
- dễ phân quyền theo từng box
- dễ vận hành hơn khi số lượng tiệm tăng lên

---

## 8. Điểm mạnh của giải pháp hiện tại

### 8.1. Tự động hóa cao

Sau khi cài và kích hoạt, người dùng hầu như không phải thao tác mỗi ngày.

### 8.2. Có giám sát tập trung

Nhờ Telegram và Google Drive, người quản lý có thể biết tình trạng backup của nhiều tiệm mà không cần vào từng máy.

### 8.3. Dễ triển khai thực tế

Giao diện đơn giản, chỉ cần nhập tên tiệm và chọn thư mục.

### 8.4. Có khả năng mở rộng

Hệ thống có thể mở rộng cho nhiều merchant vì Drive folder được tạo động theo tên tiệm.

### 8.5. Có khả năng vận hành lâu dài

App có các thành phần như retry mạng, auto-start, tray mode, report cuối ngày, nên phù hợp vận hành thực tế thay vì chỉ là tool thử nghiệm.

---

## 9. Những rủi ro hoặc điểm cần lưu ý

### 9.1. Phụ thuộc vào đường truyền mạng

Nếu mạng lỗi, upload Drive hoặc gửi Telegram có thể bị chậm hoặc thất bại. Tuy nhiên app có cơ chế retry để giảm rủi ro.

### 9.2. Phụ thuộc vào quyền Google Drive

Nếu Service Account không được cấp đúng quyền trên folder gốc, app sẽ không tạo folder hoặc upload được file.

### 9.3. Phụ thuộc vào đúng tên merchant

Nếu tên merchant nhập sai chuẩn, dữ liệu có thể lên sai folder hoặc tạo folder lệch chuẩn.

### 9.4. Secret cần quản lý tốt

Bot token và thông tin Google credential là dữ liệu nhạy cảm, cần bảo vệ cẩn thận khi triển khai thật.

---

## 10. Đánh giá tính khả thi khi có 400-500 PC backup trong khung giờ 7:00 PM - 11:00 PM

### 10.1. Kết luận ngắn gọn

Xét về mặt kiến trúc hiện tại, bài toán `400-500 PC` backup trong khung giờ `7:00 PM - 11:00 PM` là **khả thi**, nhưng chỉ khả thi tốt khi hiểu đúng mô hình tải của hệ thống.

Điểm quan trọng là app này **không dồn toàn bộ xử lý về một server trung tâm**. Mỗi máy tự làm phần việc của chính nó:

- theo dõi file `.bak`
- nén file `.bak` thành `.zip`
- tự upload lên Google Drive
- tự gửi Telegram khi thành công hoặc thất bại

Vì vậy, tải xử lý được **phân tán ra 400-500 PC**, chứ không phải một máy chủ phải xử lý 500 file cùng lúc.

### 10.2. Vì sao bài toán này khả thi

#### a. Tải tính toán được phân tán

Mỗi PC tự nén file backup trên máy local của chính nó. Điều này có nghĩa là:

- CPU nén file nằm ở từng máy
- IO đọc file `.bak` nằm ở từng máy
- không có server trung tâm phải nén 400-500 file cùng lúc

Đây là điểm rất quan trọng làm cho mô hình hiện tại có tính khả thi cao.

#### b. Upload diễn ra phân tán theo từng máy

Mỗi PC tự upload file của mình lên Google Drive. Nếu 500 máy cùng upload, thì tải chính nằm ở:

- đường truyền internet outbound của từng site
- năng lực nhận request của Google Drive API
- độ ổn định mạng tại từng máy

Vì mỗi máy chỉ upload file của riêng nó, nên về lý thuyết hệ thống có thể scale tốt hơn mô hình tập trung.

#### c. Khung thời gian 4 tiếng là tương đối rộng

Từ `7:00 PM` đến `11:00 PM` là khoảng `4 tiếng`.

Nếu có `500 PC`, trung bình chỉ cần xử lý khoảng:

- `125 PC / giờ`
- khoảng `2.1 PC / phút`

Tất nhiên thực tế không đều như vậy, vì nhiều máy có thể backup gần cùng thời điểm. Tuy nhiên xét trên khung 4 tiếng thì đây không phải mức quá cực đoan đối với mô hình phân tán hiện tại.

### 10.3. Các điểm nghẽn thực tế cần lưu ý

Dù khả thi, hệ thống vẫn có một số điểm nghẽn vận hành cần hiểu rõ.

#### a. Google Drive là điểm tập trung lớn nhất

Toàn bộ 400-500 máy cuối cùng đều upload về cùng một hệ thống lưu trữ là Google Drive.

Điều này tạo ra các rủi ro sau:

- có thể gặp quota hoặc throttling của Google API
- có thể xuất hiện lỗi tạm thời như `429`, `500`, `502`, `503`, `504`
- thời gian phản hồi của Drive có thể tăng khi nhiều máy upload cùng lúc

App hiện đã có retry mạng `3 lần`, nghỉ `15 giây` giữa các lần, đây là điểm tốt để giảm lỗi ngắn hạn. Tuy nhiên nếu Drive nghẽn kéo dài thì một số máy vẫn có thể fail.

#### b. Mỗi máy hiện xử lý tuần tự một file tại một thời điểm

Trong từng PC, app dùng `queue` và watchdog để xử lý lần lượt. Điều này tốt cho tính ổn định, nhưng cũng có nghĩa là:

- một máy không tối ưu cho nhiều file `.bak` đổ vào cùng lúc
- nếu backup bị tạo dồn nhiều file liên tiếp trên cùng một máy, thời gian chờ sẽ tăng

Tuy nhiên trong bối cảnh thông thường mỗi máy chủ yếu sinh ra một file backup chính mỗi phiên, đây không phải nút thắt lớn.

#### c. Cleanup retention làm tăng số API call

Sau mỗi lần upload, app còn gọi thêm logic kiểm tra retention để chỉ giữ `30` bản mới nhất.

Điều này có nghĩa mỗi lần backup không chỉ có upload, mà còn có thêm:

- request tìm folder
- request upload
- request list file trong folder
- request delete file cũ nếu vượt retention

Khi số lượng máy lớn, tổng số API call tăng khá nhiều. Đây là điểm cần chú ý nếu mở rộng thêm trong tương lai.

#### d. Báo cáo cuối ngày cũng quét toàn bộ Drive

Lúc `2:00 AM`, app có luồng `daily report` quét toàn bộ merchant folders và quét các file backup trong ngày để tổng hợp trạng thái.

Nếu trùng thời điểm nhiều máy vẫn đang upload mạnh, thì `daily report` có thể:

- chạy chậm hơn
- dễ gặp trễ phản hồi từ Drive hơn
- có khả năng đọc trạng thái khi một số máy chưa upload xong

Về mặt vận hành, đặt `2:00 AM` hợp lý hơn vì phần lớn backup trong khung buổi tối đã hoàn tất, nên báo cáo phản ánh dữ liệu cuối ngày đầy đủ hơn.

### 10.4. Đánh giá thực tế theo mức độ

#### Trường hợp tốt

Nếu:

- file backup của mỗi máy không quá lớn
- thời điểm phát sinh backup được phân tán tự nhiên
- mạng tại các tiệm ổn định
- Google Drive không bị throttle mạnh

thì hệ thống hiện tại hoàn toàn có thể vận hành tốt với `400-500 PC`.

#### Trường hợp áp lực cao

Nếu:

- nhiều máy cùng đẩy backup trong cùng một khung rất ngắn, ví dụ cùng 8:00 PM - 8:30 PM
- file `.bak` lớn
- mạng một số tiệm chậm hoặc chập chờn
- Drive phản hồi chậm

thì hệ thống vẫn chạy được, nhưng tỷ lệ chậm backup hoặc fail tạm thời sẽ tăng lên. Khi đó retry hiện tại giúp giảm lỗi, nhưng chưa phải cơ chế điều phối tải nâng cao.

### 10.5. Kết luận chuyên môn nên nói khi thuyết trình

Bạn có thể trả lời như sau:

> Với 400-500 PC trong khung giờ 7 giờ tối đến 11 giờ tối, kiến trúc hiện tại là khả thi vì đây là mô hình xử lý phân tán, mỗi máy tự nén và tự upload backup của chính nó chứ không dồn về một server trung tâm. Điểm nghẽn chính không nằm ở app trên từng máy mà nằm ở mạng thực tế của các tiệm và số lượng request dồn vào Google Drive trong cùng một khoảng thời gian. Vì vậy, nếu mạng ổn định và file backup không quá lớn thì hệ thống có thể chạy tốt, còn nếu quá nhiều máy dồn upload trong một khoảng ngắn thì sẽ cần theo dõi thêm về throttling, tốc độ upload và thời điểm gửi báo cáo cuối ngày.

### 10.6. Nếu muốn tăng độ chắc chắn khi scale lớn hơn

Nếu triển khai diện rộng hơn nữa, có thể cân nhắc các hướng sau:

- giãn thời điểm backup giữa các tiệm để tránh dồn upload cùng lúc
- đẩy giờ `daily report` muộn hơn để phản ánh đủ dữ liệu cuối ngày
- thêm log thống kê thời gian nén, thời gian upload, tỷ lệ retry và tỷ lệ fail
- bổ sung cơ chế retry/backoff mạnh hơn khi Google Drive trả `429`
- cân nhắc tách lớp tổng hợp báo cáo khỏi từng client nếu sau này quy mô tăng lớn hơn nhiều

---

## 11. Các câu hỏi thường gặp khi thuyết trình và gợi ý trả lời

### Câu 1: App này dùng để làm gì?

Trả lời ngắn:

App dùng để tự động sao lưu file backup của POS từ máy local lên Google Drive, đồng thời gửi thông báo và báo cáo để đội vận hành dễ theo dõi.

### Câu 2: Tại sao phải dùng app này thay vì backup thủ công?

Gợi ý trả lời:

Vì backup thủ công dễ bị quên, phụ thuộc con người và rất khó quản lý nhiều tiệm cùng lúc. App tự động hóa toàn bộ quy trình, giảm sai sót và có giám sát tập trung.

### Câu 3: App dùng công nghệ gì?

Gợi ý trả lời:

App viết bằng Python, giao diện dùng PyQt6, theo dõi file bằng watchdog, upload cloud qua Google Drive API, thông báo bằng Telegram Bot API, và chạy nền bằng nhiều thread để đảm bảo ổn định.

### Câu 4: App hoạt động theo lịch hay theo thời gian thực?

Gợi ý trả lời:

App chính hoạt động theo thời gian thực. Nó theo dõi thư mục backup và xử lý ngay khi có file `.bak` mới. Ngoài ra, báo cáo cuối ngày chạy theo mốc thời gian `2:00 AM`.

### Câu 5: App có cần người dùng mở lên mỗi ngày không?

Gợi ý trả lời:

Không nhất thiết. Sau khi cấu hình và nếu chạy bằng bản `.exe`, app có thể tự khởi động cùng Windows và tiếp tục chạy nền trong system tray.

### Câu 6: Nếu Google Drive chưa có folder của tiệm thì sao?

Gợi ý trả lời:

App sẽ tự tạo thư mục mới theo tên merchant trong thư mục gốc đã cấu hình.

### Câu 7: Nếu mạng bị lỗi thì sao?

Gợi ý trả lời:

App có cơ chế retry cho các thao tác mạng quan trọng như gửi Telegram hoặc gọi Google Drive API, nên không fail ngay ở lần đầu.

### Câu 8: Làm sao biết tiệm nào backup lỗi?

Gợi ý trả lời:

Có 3 cách: xem tin nhắn Telegram báo lỗi, xem báo cáo cuối ngày, hoặc dùng lệnh `/check` trong box report để rà lại trạng thái backup.

### Câu 9: `/list` và `/check` dùng để làm gì?

Gợi ý trả lời:

`/list` dùng để xem danh sách merchant đang có trong hệ thống Drive theo logic app. `/check` dùng để kiểm tra những tiệm chưa có backup đạt yêu cầu trong khoảng thời gian cần giám sát.

### Câu 10: Tại sao lại tách nhiều box Telegram?

Gợi ý trả lời:

Để phân luồng thông tin rõ ràng. Backup, system, report và update là các loại thông tin khác nhau. Tách riêng giúp dễ đọc, dễ quản lý và không bị trôi thông tin quan trọng.

### Câu 11: App có cập nhật được không?

Gợi ý trả lời:

Có. App có cơ chế kiểm tra update cho bản `.exe`, tải bản mới nếu phát hiện thay đổi và hỗ trợ cài đặt lại để tiếp tục vận hành.

### Câu 12: App có điểm gì nổi bật nhất?

Gợi ý trả lời:

Điểm nổi bật là tính tự động hóa từ đầu tới cuối: phát hiện backup, nén, upload, gửi thông báo, báo cáo cuối ngày và hỗ trợ kiểm tra từ xa qua Telegram.

---

## 11. Cách trình bày nhanh trong 1-2 phút

Bạn có thể nói theo mẫu này:

> Đây là ứng dụng ATLED BK, một công cụ desktop chạy trên Windows để tự động hóa việc backup dữ liệu POS của các tiệm. Sau khi kỹ thuật viên nhập tên tiệm và chọn thư mục chứa file backup, app sẽ theo dõi file `.bak` theo thời gian thực, tự nén thành `.zip`, upload lên Google Drive và gửi thông báo Telegram. Ngoài chức năng backup chính, app còn có báo cáo cuối ngày, lệnh kiểm tra từ xa như `/list` và `/check`, tự khởi động cùng Windows và hỗ trợ cập nhật ứng dụng tự động. Mục tiêu của app là giảm thao tác thủ công, giảm rủi ro quên backup và giúp đội vận hành giám sát tập trung nhiều tiệm hơn.

---

## 12. Cách trình bày chi tiết hơn trong 3-5 phút

Bạn có thể chia làm 4 ý:

### Ý 1: Bài toán

Quản lý backup thủ công cho nhiều tiệm rất dễ lỗi, dễ quên và khó kiểm tra tập trung.

### Ý 2: Giải pháp

ATLED BK tự động theo dõi thư mục backup, nén file, upload cloud và gửi thông báo.

### Ý 3: Giá trị vận hành

Có Telegram để giám sát, có báo cáo cuối ngày, có lệnh kiểm tra từ xa, có auto-start và auto-update.

### Ý 4: Lợi ích thực tế

Giảm thao tác thủ công, giảm sai sót, tiết kiệm thời gian, tăng độ tin cậy và dễ quản lý nhiều merchant.

---

## 13. Kết luận

ATLED BK không chỉ là một tool upload file backup. Đây là một ứng dụng vận hành thực tế có đầy đủ các thành phần cần thiết cho môi trường nhiều tiệm:

- tự động backup
- lưu trữ tập trung
- giám sát bằng Telegram
- báo cáo cuối ngày
- kiểm tra từ xa
- tự khởi động
- tự cập nhật

Nếu trình bày ngắn gọn, bạn có thể kết luận như sau:

> Ứng dụng ATLED BK giúp chuẩn hóa và tự động hóa toàn bộ quy trình backup POS từ máy local lên Google Drive, đồng thời bổ sung lớp giám sát và vận hành qua Telegram để đội kỹ thuật quản lý nhiều tiệm hiệu quả hơn.
