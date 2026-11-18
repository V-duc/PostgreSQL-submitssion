# Key-Value Store (Redis) - Lab: TicketRush

Nguồn: `https://cada.neu.edu.vn/courses/nosql-databases/02-key-value-store-redis`

## Tổng quan bài Lab TicketRush

Xây dựng phần lõi hệ thống đặt vé sự kiện (**TicketRush**) trên **Redis 8** với **Python (`redis-py`)**, chứng minh với 50–500 luồng đồng thời rằng hệ thống không bao giờ bán trùng ghế, không bán quá số lượng vé (`oversell`), và chống được bot spam.

| Bước | Chủ đề | Tính năng Redis |
| --- | --- | --- |
| 0 | Cài đặt môi trường | Docker (`redis:8`), `redis-py` |
| 1 | Giữ ghế và Race Condition | `SET NX EX` |
| 2 | Giữ, xác nhận, hủy giữ ghế nguyên tử | Lua scripts, Sets (`SADD`, `SMEMBERS`) |
| 3 | Flash sale vé đứng (General Admission) | `DECR`, `INCR` |
| 4 | Giới hạn tốc độ (Rate Limiting) | `INCR` + `EXPIRE NX` (Fixed window), Sorted Sets + Lua (Sliding window) |
| 5 | Phòng chờ ảo (Virtual Waiting Room) | Sorted Sets (`ZADD NX`, `ZRANK`, `ZPOPMIN`) |
| 6 | Kiểm thử chịu tải (Stress Test) | Tổng hợp (100 người tranh 20 ghế) |

---

## Thiết kế Key

| Key | Kiểu | Ý nghĩa |
| --- | --- | --- |
| `hold:{event}:{seat}` | String + TTL | Người dùng đang giữ ghế |
| `sold:{event}` | Set | Tập các ghế đã thanh toán |
| `stock:{event}` | String (counter) | Số vé đứng còn lại |
| `rl:sliding:{user}` | Sorted Set | Timestamp các request gần đây của user |
| `queue:{event}` | Sorted Set | Hàng đợi phòng chờ, score = thời điểm vào |

---

## Câu hỏi cho báo cáo

1. Ở Bước 1, vì sao `SET NX EX` tránh được race condition còn `GET` rồi mới `SET` thì không?
2. Chuyện gì xảy ra với một ghế nếu khách giữ ghế rồi đóng trình duyệt? Tính năng nào của Redis xử lý việc đó?
3. Ở Bước 2, điều gì sẽ sai nếu `confirm` không kiểm tra chủ sở hữu đang giữ ghế?
4. Khi nào fixed-window rate limiting là đủ tốt, và khi nào cần dùng sliding window?
5. Redis là lớp xử lý nhanh. Dữ liệu nào bạn cần ghi thêm xuống cơ sở dữ liệu bền vững (PostgreSQL/MySQL), và ghi vào lúc nào? (Nghĩ về trường hợp Redis bị restart giữa lúc `confirm` và lúc ghi nhận thanh toán.)

---

## Bài tập cuối bài (Exercises)

1. Xây dựng bảng xếp hạng (**Leaderboard**) bằng Sorted Set và in ra top 3 người chơi kèm thứ hạng.
2. Lưu hồ sơ người dùng (**User Profiles**) bằng Hash và tìm người dùng theo thành phố bằng Set cho mỗi thành phố.
3. Đo tốc độ tăng tốc (**Speed-up**) của mẫu **Cache-Aside** cho 100 request lặp lại.
