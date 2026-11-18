# Document Store (MongoDB) - Hướng dẫn & Bài tập

Nguồn: `https://cada.neu.edu.vn/courses/nosql-databases/01-document-store-mongodb`

## Tổng quan nội dung
- **Mô hình Document (BSON/JSON):** Database $\rightarrow$ Collection $\rightarrow$ Document $\rightarrow$ Field; tư duy **Embedding** (nhúng) vs **Referencing** (tham chiếu).
- **Khởi chạy MongoDB:** Dùng [compose.yaml](file:///d:/.A-Courses/Y3/A-DB/MongoDB/compose.yaml) (`mongo:8`, cổng `27017`) và mở shell bằng `docker compose exec mongo mongosh`.
- **CRUD & Aggregation & Index:**
  - `insertOne`, `insertMany`
  - `find(filter, projection).sort().limit()`, dot notation (`customer.city`), mảng (`items.sku`), toán tử (`$gt`, `$in`, `$exists`)
  - `updateOne`, `updateMany`, `deleteOne` với `$set`, `$push`, `$unset`
  - Aggregation Pipeline (`$match`, `$unwind`, `$group`, `$sort`, `$limit`)
  - Indexing & `explain("executionStats")` (`COLLSCAN` vs `IXSCAN`)
  - Kết nối từ Python với `pymongo`

## Bài tập (3 bài)
1. Thêm **5 đơn hàng** có hình dạng khác nhau, rồi tìm mọi đơn chứa một `sku` cho trước.
2. Viết một **aggregation** trả về **doanh thu theo thành phố**.
3. Tạo một **index** và so sánh **`explain()`** trước và sau trên **10.000 document** sinh ngẫu nhiên.
