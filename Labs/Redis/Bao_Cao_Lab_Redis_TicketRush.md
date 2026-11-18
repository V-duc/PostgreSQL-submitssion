# BÁO CÁO THỰC HÀNH LAB: KEY-VALUE STORE (REDIS - TICKETRUSH)

- **Môn học:** Cơ sở dữ liệu nâng cao (NoSQL & Vector Databases)
- **Chủ đề:** Chương 2 — Cơ sở dữ liệu Key-Value (Redis) — Lab: TicketRush
- **Môi trường:** Docker Compose (`redis:8`, cổng `6379`), Python 3.11 (`redis 8.1.0`)
- **Thư mục mã nguồn:** `D:\.A-Courses\Y3\A-DB\Redis`
- **Trạng thái kiểm thử:** Đã chạy thành công toàn bộ 6 bước và 3 bài tập trên container `redis-redis-1` (`redis:8`, cổng `6379`).

---

## PHẦN 1: THIẾT KẾ KEY & TRIỂN KHAI CÁC BƯỚC TRONG LAB

Toàn bộ mã nguồn thực thi được cài đặt tại [ticketrush.py](file:///d:/.A-Courses/Y3/A-DB/Redis/ticketrush.py) cùng cấu hình [docker-compose.yml](file:///d:/.A-Courses/Y3/A-DB/Redis/docker-compose.yml).

### Thiết kế không gian Key (Key Layout)

| Key | Kiểu dữ liệu | Mục đích |
| :--- | :--- | :--- |
| `hold:{event}:{seat}` | String + `EX` (TTL) | Lưu `user` đang giữ ghế; tự hết hạn sau 300s |
| `sold:{event}` | Set | Tập các mã ghế đã thanh toán thành công |
| `stock:{event}` | String (Counter) | Số vé đứng (General Admission) còn lại |
| `buyers:{event}` | Set | Tập các user đã mua được vé đứng |
| `rl:fixed:{user}:{window}` | String (Counter) + TTL | Bộ đếm rate limit theo cửa sổ cố định |
| `rl:sliding:{user}` | Sorted Set + `PEXPIRE` | Timestamp (ms) các request gần đây của `user` |
| `queue:{event}` | Sorted Set | Hàng đợi phòng chờ ảo, `score` = thời điểm vào |

### Tóm tắt cài đặt 6 bước trong `ticketrush.py`

1. **Bước 1 (`hold_naive` vs `hold_nx`):**
   - `hold_naive` kiểm tra `r.get(key) is None` rồi mới gọi `r.set(...)` — dễ bị **check-then-act race condition** khi 50 luồng chạy đồng thời, dẫn đến nhiều người cùng giữ 1 ghế.
   - `hold_nx` dùng lệnh nguyên tử `r.set(key, user, nx=True, ex=ttl)` nên luôn chỉ có đúng **1 người thắng** (`winners: 1`), đồng thời tự gắn TTL để ghế tự giải phóng khi hết hạn.
2. **Bước 2 (Lua Scripts `HOLD`, `CONFIRM`, `RELEASE` & `seat_map`):**
   - `HOLD`: kiểm tra ghế chưa nằm trong `sold:{event}` (`SISMEMBER`), sau đó `SET ... NX EX`.
   - `CONFIRM`: chỉ khi `GET hold:{event}:{seat} == user` mới `SADD` vào `sold:{event}` và `DEL` key giữ ghế.
   - `RELEASE`: chỉ chủ sở hữu giữ ghế mới có quyền `DEL` key giữ ghế.
   - Do chạy bằng Lua script trên Redis (single-threaded), toàn bộ chuỗi kiểm tra + ghi diễn ra **nguyên tử**.
3. **Bước 3 (`buy_general` vs `buy_general_naive`):**
   - `buy_general` dùng `r.decr(f"stock:{event}")`: nếu kết quả `< 0` thì gọi `r.incr(...)` hoàn tác và trả về `False`. Nhờ `DECR` nguyên tử, 500 luồng tranh 100 vé luôn bán đúng **100 vé**, tồn kho cuối **`0`**, không bị oversell.
4. **Bước 4 (`allow_fixed` vs `allow_sliding`):**
   - `allow_fixed` dùng `pipeline()` gom `INCR` + `EXPIRE ... NX` theo cửa sổ `int(time.time() // window)`, vẫn gặp lỗ hổng burst gấp đôi (`10` request trong `0.4s`) ngay ranh giới chuyển cửa sổ.
   - `allow_sliding` dùng Lua script trên **Sorted Set** (`ZREMRANGEBYSCORE` → `ZCARD` → `ZADD` với member `uuid.uuid4().hex` → `PEXPIRE`), chặn được burst ở biên cửa sổ.
5. **Bước 5 (Virtual Waiting Room: `join_queue`, `admit`):**
   - Dùng `ZADD ... NX` với `score = time.time()` để xếp hàng công bằng và giữ nguyên vị trí nếu user vào lại; `ZRANK` trả về thứ tự hàng đợi; `ZPOPMIN` duyệt từng nhóm `n` người đầu tiên.
6. **Bước 6 (`run_stress_test`):**
   - 100 luồng tranh 20 ghế (`S1`–`S20`) lặp lại 10 lần; kiểm chứng `assert (len(got), len(set(got)), r.scard("sold:c1")) == (20, 20, 20)` để đảm bảo không trùng ghế và không thất thoát.

---

## PHẦN 2: TRẢ LỜI 5 CÂU HỎI BÁO CÁO

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

## PHẦN 3: BÀI TẬP CUỐI BÀI (EXERCISES 1–3)

Cả 3 bài tập đã được cài đặt trong [ticketrush.py](file:///d:/.A-Courses/Y3/A-DB/Redis/ticketrush.py):
1. **Bài 1 (`exercise_1_leaderboard`):** Dùng `ZADD board ...` và `ZREVRANGE board 0 2 WITHSCORES` để lấy top 3 người chơi điểm cao nhất kèm thứ hạng.
2. **Bài 2 (`exercise_2_profiles_by_city`):** Lưu profile từng user bằng Hash (`HSET user:{uid}`) và tự tạo chỉ mục ngược theo thành phố bằng Set (`SADD city:{city} {uid}`), sau đó truy vấn tất cả user ở `"Hanoi"` qua `SMEMBERS city:Hanoi` + `HGETALL`.
3. **Bài 3 (`exercise_3_cache_aside`):** So sánh thời gian chạy 100 request đọc sản phẩm `product:7` (mô phỏng DB chậm 50ms/lần) giữa không có cache (~`5s`) và có cache-aside trên Redis (`SET ... EX 300`).

---

## PHẦN 4: KẾT QUẢ CHẠY THỰC TẾ (`python ticketrush.py`)

```text
=== Step 1: Seat holds & race condition ===
hold_naive winners (50 threads): 12
hold_nx winners (50 threads)   : 1
TTL hold:c1:A1                 : 300

=== Step 2: Atomic hold, confirm, release (Lua) ===
hold(c1, A1, linh)   : True
hold(c1, A1, nam)    : False
confirm(c1, A1, nam) : False
confirm(c1, A1, linh): True
hold(c1, A1, nam)    : False
seat_map             : {'A1': 'sold', 'A2': 'free'}
SMEMBERS sold:c1     : ['A1']

=== Step 3: Flash sale on general admission ===
buy_general_naive (sold, stock, buyers): 130 -30 130
buy_general DECR  (sold, stock, buyers): 100 0 100

=== Step 4: Rate limiting ===
allow_fixed x8: [True, True, True, True, True, False, False, False]
fixed boundary (5 before + 5 after)  : [True, True, True, True, True, True, True, True, True, True]
sliding boundary (5 before + 5 after): [True, True, True, True, True, False, False, False, False, False]

=== Step 5: Virtual waiting room ===
join u1 -> pos 1
join u2 -> pos 2
join u3 -> pos 3
re-join u1 -> pos 1
admit 2          -> ['u1', 'u2']
u3 new pos       -> 1

=== Step 6: Final stress test (10 runs) ===
Run  1: sold=20, distinct=20, set_card=20
Run  2: sold=20, distinct=20, set_card=20
Run  3: sold=20, distinct=20, set_card=20
Run  4: sold=20, distinct=20, set_card=20
Run  5: sold=20, distinct=20, set_card=20
Run  6: sold=20, distinct=20, set_card=20
Run  7: sold=20, distinct=20, set_card=20
Run  8: sold=20, distinct=20, set_card=20
Run  9: sold=20, distinct=20, set_card=20
Run 10: sold=20, distinct=20, set_card=20

=== Exercises 1, 2, 3 ===
Ex 1 Leaderboard: [(1, 'mai', 1430), (2, 'binh', 1350), (3, 'linh', 1200)]
Ex 2 Hanoi users: {'u1': {'name': 'Linh', 'city': 'Hanoi', 'age': '21'}, 'u3': {'name': 'Mai', 'city': 'Hanoi', 'age': '20'}}
Ex 3 Cache-aside (100 reqs): no_cache=5.052s, with_cache=0.1018s, speedup=49.6x
```
