# BÁO CÁO THỰC HÀNH LAB: KEY-VALUE STORE (REDIS - TICKETRUSH)

## TRẢ LỜI 5 CÂU HỎI BÁO CÁO

### Câu 1: Ở Bước 1, vì sao `SET NX EX` tránh được race condition còn `GET` rồi mới `SET` thì không?
- Khi dùng `GET` rồi mới `SET`, hai thao tác là **hai lệnh riêng biệt** gửi qua mạng: nhiều luồng có thể cùng đọc thấy `GET` trả về `None` trước khi bất kỳ luồng nào kịp ghi `SET`, dẫn đến nhiều người cùng ghi đè và tưởng mình đã giữ được ghế (**check-then-act race condition**).
- Lệnh `SET key value NX EX ttl` gộp cả **kiểm tra tồn tại (`NX`)**, **ghi giá trị**, và **đặt thời gian hết hạn (`EX`)** thành **một lệnh đơn nguyên tử** thực thi tuần tự trong vòng lặp sự kiện đơn luồng của Redis; chỉ luồng đến đầu tiên nhận được `OK` (`True`), mọi luồng sau đều nhận `nil` (`False`).

### Câu 2: Chuyện gì xảy ra với một ghế nếu khách giữ ghế rồi đóng trình duyệt? Tính năng nào của Redis xử lý việc đó?
- Khách không bấm xác nhận thanh toán nên `hold:{event}:{seat}` không bị xóa thủ công, nhưng nhờ **TTL / Key Expiration (`EX 300`)**, sau 300 giây Redis **tự động xóa** key `hold:{event}:{seat}` và ghế tự động trở về trạng thái `free` cho người khác đặt mà không cần viết cronjob dọn dẹp.

### Câu 3: Ở Bước 2, điều gì sẽ sai nếu `confirm` không kiểm tra chủ sở hữu đang giữ ghế?
- Có hai lỗi nghiêm trọng xảy ra:
  1. **Người khác chiếm/xác nhận nhầm ghế:** User B có thể gọi `confirm` cho ghế đang được User A giữ và cướp mất ghế của A.
  2. **Xác nhận sau khi hết hạn giữ ghế (Expired Hold):** User A giữ ghế nhưng thanh toán chậm quá TTL 300s; ghế hết hạn và được User B giữ hợp lệ. Nếu A gửi `confirm` muộn mà không kiểm tra chủ sở hữu (`GET == user`), lệnh `confirm` của A sẽ đánh dấu ghế là `sold` cho A và xóa key giữ ghế của B, gây **bán trùng / tranh chấp ghế**.

### Câu 4: Khi nào fixed-window rate limiting là đủ tốt, và khi nào cần dùng sliding window?
- **Fixed window đủ tốt** khi hệ thống chỉ cần chống spam mức cơ bản, chấp nhận được việc người dùng có thể gửi tối đa gấp `2x` giới hạn ngay tại thời điểm chuyển giao giữa hai cửa sổ thời gian (ví dụ: đếm lượt gọi API thông thường, giới hạn nhẹ), và cần tiết kiệm RAM (chỉ tốn 1 counter nhỏ cho mỗi user).
- **Sliding window cần thiết** khi phải thực thi giới hạn **nghiêm ngặt** trên mọi khoảng thời gian trượt (không cho phép burst `2x` ở biên cửa sổ), chẳng hạn chống bot săn vé flash sale, chống brute-force đăng nhập / OTP, hoặc bảo vệ endpoint thanh toán.

### Câu 5: Redis là lớp xử lý nhanh. Dữ liệu nào bạn cần ghi thêm xuống cơ sở dữ liệu bền vững (PostgreSQL/MySQL), và ghi vào lúc nào?
- **Dữ liệu cần ghi xuống CSDL bền vững:** Toàn bộ **đơn hàng đã thanh toán, thông tin vé đã bán (`sold`), giao dịch thanh toán, và lịch sử người mua** (những dữ liệu mang tính hệ thống chuẩn — *system of record* — không được phép mất).
- **Thời điểm ghi:** Ghi xuống PostgreSQL/MySQL trong giao dịch thanh toán khi chuyển từ giữ ghế sang xác nhận bán (`confirm` / bước hoàn tất thanh toán). Nếu Redis bị restart hoặc mất dữ liệu ngay sau `confirm` mà chưa kịp ghi xuống DB quan hệ (vì RDB/AOF vẫn có thể mất vài giây dữ liệu gần nhất), khách đã trả tiền nhưng mất vé hoặc ghế bị mở bán lại; do đó cần ghi bền vững vào PostgreSQL/MySQL trước khi báo đặt vé thành công (hoặc đồng bộ qua giao dịch/outbox), còn Redis chỉ giữ vai trò lớp tăng tốc và khóa tạm thời.

---

Ex 3 Cache-aside (100 reqs): no_cache=5.052s, with_cache=0.1018s, speedup=49.6x
```
