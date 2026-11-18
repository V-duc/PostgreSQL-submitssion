# BÁO CÁO THỰC HÀNH LAB: DOCUMENT STORE (MONGODB)

- **Môn học:** Cơ sở dữ liệu nâng cao (NoSQL & Vector Databases)
- **Chủ đề:** Chương 1 — Cơ sở dữ liệu Document (MongoDB)
- **Môi trường thực nghiệm:** Docker Compose (`mongo:8`, cổng `27017`), `mongosh` & Python (`pymongo`)
- **Thư mục mã nguồn:** `D:\.A-Courses\Y3\A-DB\MongoDB`

---

## PHẦN 1: TỔNG QUAN MÔ HÌNH & TRIỂN KHAI

1. **Khởi chạy MongoDB (`compose.yaml`):**
   ```powershell
   docker compose -f compose.yaml up -d
   docker compose -f compose.yaml exec mongo mongosh
   ```
   Chọn database `shop` (tự động khởi tạo ở lần ghi đầu tiên):
   ```javascript
   use shop
   ```

2. **Đặc điểm mô hình Document:**
   - Dữ liệu lưu dưới dạng **BSON** (JSON nhị phân) trong các **Collection**.
   - Ưu tiên **Embedding (nhúng)** các dữ liệu thường xuyên đọc cùng nhau (như mảng `items` nằm bên trong document `orders`) để chỉ cần 1 lần đọc duy nhất mà không cần `JOIN`, đồng thời đảm bảo tính **atomic** ở cấp độ từng document.
   - Cho phép **Schema linh hoạt** (mỗi document trong cùng collection có thể có các field khác nhau như `coupon`, `giftWrap`, `tags`, `note`).

---

## PHẦN 2: LỜI GIẢI 3 BÀI TẬP THỰC HÀNH

Toàn bộ mã nguồn thực thi được lưu tại:
- Script `mongosh`: [mongodb_exercises.js](file:///d:/.A-Courses/Y3/A-DB/MongoDB/mongodb_exercises.js)
- Script Python (`pymongo`): [mongodb_lab.py](file:///d:/.A-Courses/Y3/A-DB/MongoDB/mongodb_lab.py)

### Bài tập 1: Thêm 5 đơn hàng có hình dạng khác nhau, rồi tìm mọi đơn chứa một `sku` cho trước

- **Thiết kế 5 đơn hàng mới (`_id` từ `1004` đến `1008`):**
  Mỗi đơn có tập các trường khác nhau: đơn `1004` có `customer.tier` và `note`; đơn `1005` có `customer.phone` và `giftWrap`; đơn `1006` có `paymentMethod`; đơn `1007` có `coupon` và `discount`; đơn `1008` có `tags`.
- **Truy vấn tìm mọi đơn hàng chứa `sku: "BK-01"`:**
  ```javascript
  db.orders.find(
    { "items.sku": "BK-01" },
    { _id: 1, "customer.name": 1, "customer.city": 1, status: 1, "items.sku": 1 }
  ).sort({ _id: 1 });
  ```
  - Kết quả trả về 4 đơn hàng chứa `BK-01`: `_id: 1001` (Linh), `_id: 1003` (Mai), `_id: 1004` (Hung), `_id: 1006` (Binh).

---

### Bài tập 2: Viết một Aggregation Pipeline trả về doanh thu theo thành phố

- **Pipeline (lọc các đơn đã thanh toán/giao hàng `paid` hoặc `shipped`, tách mảng `items` bằng `$unwind`, gom nhóm theo `customer.city`):**
  ```javascript
  db.orders.aggregate([
    { $match: { status: { $in: ["paid", "shipped"] } } },
    { $unwind: "$items" },
    {
      $group: {
        _id: "$customer.city",
        totalOrders: { $addToSet: "$_id" },
        totalUnits: { $sum: "$items.qty" },
        revenue: { $sum: { $multiply: ["$items.qty", "$items.price"] } }
      }
    },
    {
      $project: {
        _id: 0,
        city: "$_id",
        orderCount: { $size: "$totalOrders" },
        totalUnits: 1,
        revenue: { $round: ["$revenue", 2] }
      }
    },
    { $sort: { revenue: -1, city: 1 } }
  ]);
  ```
- **Kết quả tính toán trên 8 đơn hàng mẫu (bỏ qua đơn `1006` ở trạng thái `pending`):**
  - `HCMC`: 2 đơn (`1005`, `1008`), 5 sản phẩm $\rightarrow$ doanh thu `$121.0`
  - `Hue`: 1 đơn (`1004`), 4 sản phẩm $\rightarrow$ doanh thu `$62.5`
  - `Da Nang`: 2 đơn (`1002`, `1007`), 2 sản phẩm $\rightarrow$ doanh thu `$57.0`
  - `Hanoi`: 2 đơn (`1001`, `1003`), 4 sản phẩm $\rightarrow$ doanh thu `$55.5`

---

### Bài tập 3: Tạo Index và so sánh `explain()` trước & sau trên 10.000 document sinh ngẫu nhiên

- **Kịch bản kiểm thử:**
  1. Sinh 10.000 document ngẫu nhiên vào collection `orders_bench` (5 thành phố $\times$ 4 trạng thái).
  2. Chạy truy vấn `db.orders_bench.find({ "customer.city": "Hanoi", status: "paid" }).explain("executionStats")` **trước khi tạo index**.
  3. Tạo Compound Index:
     ```javascript
     db.orders_bench.createIndex({ "customer.city": 1, status: 1 });
     ```
  4. Chạy lại `explain("executionStats")` **sau khi tạo index**.

- **So sánh cơ chế thực thi (Query Plan):**

  | Tiêu chí | Trước khi có Index | Sau khi có Compound Index `{"customer.city": 1, status: 1}` |
  | :--- | :--- | :--- |
  | **Stage chính** | `COLLSCAN` (Collection Scan) | `FETCH` $\leftarrow$ `IXSCAN` (Index Scan) |
  | **`totalDocsExamined`** | **10.000** (quét 100% collection) | **$\approx 500$** (chỉ đọc đúng số document khớp) |
  | **`totalKeysExamined`** | **0** | **$\approx 500$** (tra cứu trực tiếp trên B-Tree index) |
  | **Hiệu quả khi mở rộng** | Giảm tuyến tính $O(N)$ khi dữ liệu tăng | Nhanh ổn định $O(\log N + k)$ |

---

## PHẦN 3: HƯỚNG DẪN CHẠY LẠI KIỂM CHỨNG

```powershell
cd D:\.A-Courses\Y3\A-DB\MongoDB
docker compose -f compose.yaml up -d
docker compose -f compose.yaml exec -T mongo mongosh < mongodb_exercises.js
```
Hoặc chạy bằng Python (`pymongo`):
```powershell
pip install pymongo
python mongodb_lab.py
```
