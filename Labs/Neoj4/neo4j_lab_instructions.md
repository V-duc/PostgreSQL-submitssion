# Graph Database (Neo4j) - Lab: CampusGraph

Nguồn: `https://cada.neu.edu.vn/courses/nosql-databases/04-graph-database-neo4j`

## Tổng quan bài Lab CampusGraph

Xây dựng công cụ lập kế hoạch học tập và mạng lưới bạn bè sinh viên trên **Neo4j 5** với **Python (`neo4j` driver)**.

### Mô hình đồ thị (Property Graph Schema)
- **Nodes:**
  - `(:Student {id, name, year})`: 10 sinh viên (`S01` – `S10`), có Unique Constraint `student_id` trên `s.id`.
  - `(:Course {code, title, credits})`: 13 môn học (`CS101` – `CAP401`), có Unique Constraint `course_code` trên `c.code`.
- **Relationships:**
  - `(:Course)-[:REQUIRES]->(:Course)`: Môn học yêu cầu môn tiên quyết trực tiếp.
  - `(:Student)-[:PASSED {grade}]->(:Course)`: Sinh viên đã qua môn học với điểm `grade`.
  - `(:Student)-[:FRIEND]->(:Student)`: Quan hệ bạn bè giữa hai sinh viên (lưu 1 chiều, truy vấn 2 chiều).

---

## Các bước thực hiện

### Bước 0: Khởi chạy Neo4j và nạp dữ liệu
```powershell
docker compose up -d
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install "neo4j>=5.20" pandas
python campus.py setup
```

### Bước 1 – 7: Cài đặt 7 hàm truy vấn trong `campus.py`
1. **Task 1 (`passed_courses(student_id)`):** Trả về `[(code, grade), ...]` các môn sinh viên đã qua, sắp xếp theo `grade DESC, code ASC`.
2. **Task 2 (`prerequisite_chain(code)`):** Trả về `[(code, depth), ...]` mọi môn tiên quyết trực tiếp và gián tiếp kèm số bước `REQUIRES` nhỏ nhất (`min(length(path))`), sắp xếp theo `depth ASC, code ASC`.
3. **Task 3 (`eligible_courses(student_id)`):** Trả về `[code, ...]` các môn sinh viên chưa qua và đã qua mọi môn tiên quyết trực tiếp (`NOT EXISTS`), sắp xếp theo `code ASC`.
4. **Task 4 (`suggest_friends(student_id, k=3)`):** Gợi ý tối đa `k` sinh viên chưa kết bạn (theo cả 2 chiều), xếp hạng theo số môn cùng đã qua giảm dần (`shared DESC, name ASC`).
5. **Task 5 (`connection(a_id, b_id)`):** Trả về danh sách tên sinh viên trên đường đi bạn bè ngắn nhất (`shortestPath((a)-[:FRIEND*]-(b))`, bỏ qua hướng).
6. **Task 6 (`bottleneck_courses(k=3)`):** Trả về `[(code, dependents), ...]` top `k` môn học có nhiều môn khác phụ thuộc vào nó nhất (trực tiếp hoặc gián tiếp).
7. **Task 7 (`record_pass(student_id, code, grade)` / `_record_pass_tx`):** Trong **1 write transaction** duy nhất (`session.execute_write`), kiểm tra sinh viên & môn học tồn tại, kiểm tra không thiếu môn tiên quyết trực tiếp, rồi `MERGE` quan hệ `PASSED` và cập nhật `grade`.

Kiểm tra tự động:
```powershell
python campus.py check
```

### Bước 8: Xem Query Plan (`PROFILE`)
Chạy `PROFILE` cho truy vấn Task 3 với `"S01"` khi có và không có constraint `student_id`:
```cypher
DROP CONSTRAINT student_id;
// Chạy PROFILE truy vấn Task 3
CREATE CONSTRAINT student_id IF NOT EXISTS FOR (s:Student) REQUIRE s.id IS UNIQUE;
```

---

## Câu hỏi cho báo cáo
1. Viết các bảng SQL cho bộ dữ liệu này và truy vấn SQL cho Task 2 (dùng `WITH RECURSIVE`). So sánh độ dài và độ dễ đọc với truy vấn Cypher.
2. Ở Task 2, vì sao truy vấn chỉ trả về mỗi môn tiên quyết một lần sau khi tổng hợp? Có bao nhiêu đường đi từ `CAP401` tới `CS101`?
3. Ở Bước 8, operator đầu tiên khi có và không có constraint là gì, và bao nhiêu `db hits`? Điều gì sẽ xảy ra với 100.000 sinh viên?
4. Vì sao `FRIEND` chỉ được lưu theo một chiều? Điều gì sẽ sai ở Task 4 và Task 5 nếu lưu cả hai chiều mà giữ nguyên truy vấn?
5. Trường muốn lưu mọi lần học một môn (sinh viên có thể trượt và học lại ở các học kỳ khác nhau). Hãy thiết kế lại mô hình (`:Enrollment` node vs property trên relationship) và viết lại truy vấn Task 1.
6. Ở Task 7, điều gì sẽ sai nếu bước kiểm tra tiên quyết và bước ghi chạy trong hai lời gọi `execute_query` riêng, trong khi một chương trình khác đang xoá các relationship `PASSED` cùng lúc?
