# Column-Family Database (Cassandra) - Lab: SensorRing

Nguồn: `https://cada.neu.edu.vn/courses/nosql-databases/03-column-family-cassandra#b%C6%B0%E1%BB%9Bc-0-d%E1%BB%B1ng-cluster`

## Tổng quan các bước trong Lab

| Bước | Kiểm chứng điều gì | Công cụ | Thời gian |
| --- | --- | --- | --- |
| 0 | Dựng cluster 3 node, nạp dữ liệu | Docker Compose, Python | 15 phút (chủ yếu chờ) |
| 1 | Partition key quyết định node nào lưu hàng | `token()`, `nodetool` | 10 phút |
| 2 | Truy vấn theo partition so với quét toàn bảng | `TRACING ON` | 10 phút |
| 3 | Mất node thì mức consistency nào còn chạy | `docker compose stop` | 10 phút |
| 4 | Bản sao bị cũ và cách Cassandra sửa | `nodetool`, `CONSISTENCY` | 15 phút |

---

## Bước 0: Dựng cluster

1. Đảm bảo cổng `9042` đang trống (`docker compose down` các container Cassandra cũ nếu có).
2. Khởi chạy cluster 3 node (`cass1`, `cass2`, `cass3`):
   ```powershell
   docker compose up -d
   docker compose exec cass1 nodetool status
   ```
   Chờ đến khi cả 3 dòng bắt đầu bằng `UN` (Up, Normal).
3. Ghi lại IP của từng container:
   ```powershell
   docker inspect -f '{{.Name}} {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' (docker compose ps -q)
   ```
4. Tạo môi trường ảo Python và cài đặt `cassandra-driver`:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install "cassandra-driver>=3.29"
   ```
5. Chạy script nạp 3000 dòng dữ liệu (30 cảm biến × 100 bản ghi) vào keyspace `iot` (RF = 3):
   ```powershell
   python sensorring.py load
   ```

---

## Bước 1: Partition key quyết định node

1. Xem giá trị băm `token()` (Murmur3 64-bit) của các `sensor_id`:
   ```powershell
   docker compose exec cass1 cqlsh -e "SELECT DISTINCT sensor_id, token(sensor_id) FROM iot.readings_by_sensor LIMIT 5;"
   ```
2. Kiểm tra node giữ partition `hn-01` trên keyspace `iot` (RF = 3 -> cả 3 node đều giữ):
   ```powershell
   docker compose exec cass1 nodetool getendpoints iot readings_by_sensor hn-01
   ```
3. Tạo keyspace `ring1` với `replication_factor: 1` để thấy rõ dữ liệu được chia ra các node:
   ```powershell
   docker compose exec cass1 cqlsh -e "CREATE KEYSPACE ring1 WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}; CREATE TABLE ring1.sensors (sensor_id text PRIMARY KEY);"
   ```
4. Kiểm tra node lưu từng cảm biến từ `hn-01` đến `hn-06` và tỉ lệ sở hữu (`Owns`):
   ```powershell
   foreach ($s in "hn-01","hn-02","hn-03","hn-04","hn-05","hn-06") {
       $ep = (docker compose exec -T cass1 nodetool getendpoints ring1 sensors $s) -join " "
       Write-Output "$s -> $ep"
   }
   docker compose exec cass1 nodetool status ring1
   ```
5. In vòng token (`nodetool ring`) và kiểm chứng quy tắc "node kế tiếp theo chiều kim đồng hồ" (token đầu tiên >= token của `hn-01`):
   ```powershell
   docker compose exec cass1 nodetool ring
   ```

---

## Bước 2: Truy vấn theo partition so với quét toàn bảng

1. Thử truy vấn bỏ qua partition key (sẽ báo lỗi `InvalidRequest` yêu cầu `ALLOW FILTERING`):
   ```powershell
   docker compose exec cass1 cqlsh -e "SELECT * FROM iot.readings_by_sensor WHERE temperature > 31.5;"
   ```
2. So sánh `TRACING ON` giữa truy vấn có partition key và truy vấn dùng `ALLOW FILTERING`:
   ```powershell
   docker compose exec -T cass1 cqlsh -e "CONSISTENCY ONE; TRACING ON; SELECT ts, temperature FROM iot.readings_by_sensor WHERE sensor_id = 'hn-01' LIMIT 3;" | Select-String "Executing|live rows|Request complete"

   docker compose exec -T cass1 cqlsh -e "CONSISTENCY ONE; TRACING ON; SELECT count(*) FROM iot.readings_by_sensor WHERE temperature > 31.5 ALLOW FILTERING;" | Select-String "range requests|Executing|live rows|Request complete"
   ```

---

## Bước 3: Mất node thì mức consistency nào còn chạy

1. Khi cả 3 node đều sống (`UN`):
   ```powershell
   python sensorring.py cl
   ```
2. Tắt 1 node (`cass3`), chờ `nodetool status` hiện `DN` (Down) cho `cass3`, rồi chạy lại:
   ```powershell
   docker compose stop cass3
   docker compose exec cass1 nodetool status
   python sensorring.py cl
   ```
3. Tắt thêm node thứ 2 (`cass2`), chờ `nodetool status` hiện 2 dòng `DN`, rồi chạy lại:
   ```powershell
   docker compose stop cass2
   docker compose exec cass1 nodetool status
   python sensorring.py cl
   ```

---

## Bước 4: Bản sao bị cũ và cách Cassandra sửa

1. Bật lại `cass2`, chờ trạng thái `(healthy)` rồi tắt `hinted handoff` trên `cass1` và `cass2` (trong khi `cass3` vẫn đang tắt):
   ```powershell
   docker compose start cass2
   docker compose ps
   docker compose exec cass1 nodetool disablehandoff
   docker compose exec cass2 nodetool disablehandoff
   ```
2. Ghi một số đo mới (`hn-99`) ở mức `QUORUM` (chỉ ghi vào `cass1` và `cass2`):
   ```powershell
   docker compose exec cass1 cqlsh -e "CONSISTENCY QUORUM; INSERT INTO iot.readings_by_sensor (sensor_id, ts, temperature, humidity) VALUES ('hn-99', '2026-11-01 09:00:00', 41.0, 30);"
   ```
3. Bật `cass3` lên (chờ `(healthy)`), tắt `cass1` và `cass2`, sau đó đọc `hn-99` ở mức `ONE` từ `cass3` (sẽ trả về `0 rows` - dữ liệu cũ):
   ```powershell
   docker compose start cass3
   docker compose ps
   docker compose stop cass1 cass2
   docker compose exec cass3 cqlsh -e "CONSISTENCY ONE; SELECT * FROM iot.readings_by_sensor WHERE sensor_id = 'hn-99';"
   ```
4. Bật lại `cass1` và `cass2` (chờ cả 3 `(healthy)`), đọc ở mức `ALL` để kích hoạt **Read Repair**:
   ```powershell
   docker compose start cass1 cass2
   docker compose ps
   docker compose exec cass3 cqlsh -e "CONSISTENCY ALL; SELECT * FROM iot.readings_by_sensor WHERE sensor_id = 'hn-99';"
   ```
5. Chạy **Anti-Entropy Repair** bằng `nodetool repair`:
   ```powershell
   docker compose exec cass3 nodetool repair iot
   ```
6. Dọn dẹp sau khi hoàn thành:
   ```powershell
   docker compose down -v
   ```

---

## Câu hỏi cho báo cáo

1. Ở Bước 1, vì sao token của `hn-01` trên máy bạn giống ví dụ, còn IP của node sở hữu nó thì khác?
2. Nếu thêm node `cass4` vào cluster có keyspace `ring1`, điều gì xảy ra với các partition hiện có? Có phải di chuyển toàn bộ dữ liệu không?
3. Ở Bước 2, truy vấn `ALLOW FILTERING` đọc bao nhiêu hàng để trả về bao nhiêu hàng? Hãy thiết kế một bảng trả lời “các số đo trên 31.5°C trong một ngày” mà không cần `ALLOW FILTERING`.
4. Lập bảng kết quả Bước 3 (số node sống × mức consistency). Với RF = 5, QUORUM cần bao nhiêu bản sao, và chịu được mất bao nhiêu node?
5. Ở Bước 4, nếu cả lần ghi và lần đọc đều dùng `QUORUM` thì có đọc phải dữ liệu cũ không? Giải thích bằng điều kiện R + W > RF.
6. Hệ thống IoT chấp nhận mất vài số đo nhưng không được ngừng nhận dữ liệu. Bạn chọn mức consistency nào cho ghi, và vì sao?
