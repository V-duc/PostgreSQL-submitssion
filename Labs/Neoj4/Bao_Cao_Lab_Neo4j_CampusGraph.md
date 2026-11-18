# BÁO CÁO THỰC HÀNH LAB: GRAPH DATABASE (NEO4J - CAMPUSGRAPH)

- **Môn học:** Cơ sở dữ liệu nâng cao (NoSQL & Vector Databases)
- **Chủ đề:** Chương 4 - Graph Database (Neo4j) — Lab: CampusGraph
- **Môi trường thực nghiệm:** Docker Compose (`neo4j:5`), Python 3.11 (`neo4j` driver)
- **Thư mục mã nguồn:** `D:\.A-Courses\Y3\A-DB\neoj4`

---

## PHẦN 1: KẾT QUẢ THỰC HIỆN CÁC BƯỚC TRONG LAB

### Bước 0: Khởi chạy Neo4j 5 và Nạp Dữ Liệu Mẫu (`setup`)

1. **Khởi chạy container Neo4j 5 (`docker compose up -d`):**
   ```text
   CONTAINER ID   IMAGE     COMMAND                  STATUS          PORTS                                              NAMES
   69134e082dd8   neo4j:5   "tini -g -- /startup…"   Up 15 minutes   0.0.0.0:7474->7474/tcp, 0.0.0.0:7687->7687/tcp     neoj4-neo4j-1
   ```

2. **Nạp dữ liệu đồ thị (`python campus.py setup`):**
   - Tạo 2 Unique Constraints: `student_id` trên `(:Student).id` và `course_code` trên `(:Course).code`.
   - Nạp theo lô (`UNWIND` + `MERGE`) 13 môn học (`Course`), 16 quan hệ tiên quyết (`REQUIRES`), 10 sinh viên (`Student`), các môn đã qua (`PASSED {grade}`) và 11 quan hệ bạn bè (`FRIEND`).
   - Kết quả:
     ```text
     loaded: {'Course': 13, 'Student': 10}
     ```

---

### Bước 1 – 7: Kết Quả Kiểm Thử Tự Động 7 Task (`python campus.py check`)

Toàn bộ 7 hàm trong [campus.py](file:///d:/.A-Courses/Y3/A-DB/neoj4/campus.py) đã được cài đặt bằng Cypher tham số hóa (`$sid`, `$code`, `$k`, `$grade`) và vượt qua toàn bộ bộ kiểm thử tự động:

```text
loaded: {'Course': 13, 'Student': 10}
PASS  1 passed_courses
PASS  2 prerequisite_chain
PASS  3 eligible_courses
PASS  4 suggest_friends
PASS  5 connection
PASS  6 bottleneck_courses
PASS  7a record_pass refuses
PASS  7b record_pass writes
```

#### Tóm tắt giải pháp Cypher cho 7 Task:
1. **Task 1 (`passed_courses`):**
   ```cypher
   MATCH (:Student {id: $sid})-[p:PASSED]->(c:Course)
   RETURN c.code AS code, p.grade AS grade
   ORDER BY grade DESC, code ASC
   ```
2. **Task 2 (`prerequisite_chain`):**
   ```cypher
   MATCH path = (:Course {code: $code})-[:REQUIRES*1..]->(p:Course)
   RETURN p.code AS code, min(length(path)) AS depth
   ORDER BY depth ASC, code ASC
   ```
3. **Task 3 (`eligible_courses`):**
   ```cypher
   MATCH (s:Student {id: $sid}), (c:Course)
   WHERE NOT (s)-[:PASSED]->(c)
     AND NOT EXISTS {
       MATCH (c)-[:REQUIRES]->(pre:Course)
       WHERE NOT (s)-[:PASSED]->(pre)
     }
   RETURN c.code AS code
   ORDER BY code ASC
   ```
4. **Task 4 (`suggest_friends`):**
   ```cypher
   MATCH (s:Student {id: $sid})-[:PASSED]->(c:Course)<-[:PASSED]-(other:Student)
   WHERE other <> s AND NOT (s)-[:FRIEND]-(other)
   RETURN other.name AS name, count(DISTINCT c) AS shared
   ORDER BY shared DESC, name ASC
   LIMIT $k
   ```
5. **Task 5 (`connection`):**
   ```cypher
   MATCH (a:Student {id: $a_id}), (b:Student {id: $b_id})
   OPTIONAL MATCH path = shortestPath((a)-[:FRIEND*]-(b))
   RETURN [n IN nodes(path) | n.name] AS names
   ```
6. **Task 6 (`bottleneck_courses`):**
   ```cypher
   MATCH (dep:Course)-[:REQUIRES*1..]->(c:Course)
   RETURN c.code AS code, count(DISTINCT dep) AS dependents
   ORDER BY dependents DESC, code ASC
   LIMIT $k
   ```
7. **Task 7 (`record_pass` / `_record_pass_tx`):**
   Thực thi trong 1 Managed Write Transaction (`session.execute_write`):
   - Kiểm tra `(s:Student {id: $sid}), (c:Course {code: $code})` tồn tại; nếu không ném `ValueError("unknown student or course: ...")`.
   - Kiểm tra danh sách môn tiên quyết trực tiếp chưa qua; nếu có ném `ValueError(f"missing prerequisites: {missing}")`.
   - Dùng `MERGE (s)-[p:PASSED]->(c) SET p.grade = $grade` để ghi nhận hoặc cập nhật điểm mà không tạo cạnh trùng lặp.

---

### Bước 8: Phân Tích Query Plan Với `PROFILE` (Có và Không Có Constraint)

Chạy `PROFILE` cho truy vấn Task 3 với `sid = 'S01'` trước và sau khi xóa constraint `student_id`:

#### 1. Khi CÓ constraint `student_id` (`IS UNIQUE`):
```text
=== WITH student_id CONSTRAINT ===
ProduceResults@neo4j |  (dbHits=0, rows=4)
  Sort@neo4j |  (dbHits=0, rows=4)
    Projection@neo4j |  (dbHits=4, rows=4)
      AntiSemiApply@neo4j |  (dbHits=0, rows=4)
        AntiSemiApply@neo4j |  (dbHits=0, rows=7)
          CartesianProduct@neo4j |  (dbHits=0, rows=13)
            NodeUniqueIndexSeek@neo4j |  (dbHits=2, rows=1)
            NodeByLabelScan@neo4j |  (dbHits=14, rows=13)
          Expand(Into)@neo4j |  (dbHits=93, rows=0)
            Argument@neo4j |  (dbHits=0, rows=13)
        Filter@neo4j |  (dbHits=3, rows=0)
          AntiSemiApply@neo4j |  (dbHits=0, rows=3)
            Expand(All)@neo4j |  (dbHits=31, rows=11)
              Argument@neo4j |  (dbHits=0, rows=7)
            Expand(Into)@neo4j |  (dbHits=90, rows=0)
              Argument@neo4j |  (dbHits=0, rows=11)
TOTAL dbHits: 237
```

#### 2. Khi KHÔNG CÓ constraint `student_id` (`DROP CONSTRAINT student_id`):
```text
=== WITHOUT student_id CONSTRAINT ===
ProduceResults@neo4j |  (dbHits=0, rows=4)
  Sort@neo4j |  (dbHits=0, rows=4)
    Projection@neo4j |  (dbHits=4, rows=4)
      AntiSemiApply@neo4j |  (dbHits=0, rows=4)
        AntiSemiApply@neo4j |  (dbHits=0, rows=7)
          CartesianProduct@neo4j |  (dbHits=0, rows=13)
            Filter@neo4j |  (dbHits=10, rows=1)
              NodeByLabelScan@neo4j |  (dbHits=11, rows=10)
            NodeByLabelScan@neo4j |  (dbHits=14, rows=13)
          Expand(Into)@neo4j |  (dbHits=93, rows=0)
            Argument@neo4j |  (dbHits=0, rows=13)
        Filter@neo4j |  (dbHits=3, rows=0)
          AntiSemiApply@neo4j |  (dbHits=0, rows=3)
            Expand(All)@neo4j |  (dbHits=31, rows=11)
              Argument@neo4j |  (dbHits=0, rows=7)
            Expand(Into)@neo4j |  (dbHits=90, rows=0)
              Argument@neo4j |  (dbHits=0, rows=11)
TOTAL dbHits: 256
```

---

## PHẦN 2: TRẢ LỜI 6 CÂU HỎI BÁO CÁO

### Câu 1: Viết các bảng SQL cho bộ dữ liệu này và truy vấn SQL cho Task 2 (dùng `WITH RECURSIVE`). So sánh độ dài và độ dễ đọc với truy vấn Cypher.

- **Lược đồ các bảng SQL tương đương (5 bảng):**
  ```sql
  CREATE TABLE students (
      id   VARCHAR(10) PRIMARY KEY,
      name VARCHAR(100) NOT NULL,
      year INT NOT NULL
  );

  CREATE TABLE courses (
      code    VARCHAR(20) PRIMARY KEY,
      title   VARCHAR(200) NOT NULL,
      credits INT NOT NULL
  );

  CREATE TABLE requires (
      course_code       VARCHAR(20) REFERENCES courses(code),
      prerequisite_code VARCHAR(20) REFERENCES courses(code),
      PRIMARY KEY (course_code, prerequisite_code)
  );

  CREATE TABLE passed (
      student_id  VARCHAR(10) REFERENCES students(id),
      course_code VARCHAR(20) REFERENCES courses(code),
      grade       NUMERIC(3,1) NOT NULL,
      PRIMARY KEY (student_id, course_code)
  );

  CREATE TABLE friends (
      student_a VARCHAR(10) REFERENCES students(id),
      student_b VARCHAR(10) REFERENCES students(id),
      PRIMARY KEY (student_a, student_b),
      CHECK (student_a < student_b)
  );
  ```

- **Truy vấn SQL cho Task 2 (`prerequisite_chain`) dùng `WITH RECURSIVE`:**
  ```sql
  WITH RECURSIVE prereq_paths AS (
      -- Bước cơ sở (depth = 1): tiên quyết trực tiếp
      SELECT r.prerequisite_code AS code, 1 AS depth
      FROM requires r
      WHERE r.course_code = 'CAP401'

      UNION ALL

      -- Bước đệ quy (depth + 1): tiên quyết của tiên quyết
      SELECT r.prerequisite_code AS code, p.depth + 1 AS depth
      FROM prereq_paths p
      JOIN requires r ON r.course_code = p.code
  )
  SELECT code, MIN(depth) AS depth
  FROM prereq_paths
  GROUP BY code
  ORDER BY depth ASC, code ASC;
  ```

- **So sánh với Cypher:**
  - **Độ dài:** SQL cần **18 dòng** (gồm khối `WITH RECURSIVE`, phần base case, `UNION ALL`, phép `JOIN` đệ quy, và truy vấn ngoài `GROUP BY`), trong khi Cypher chỉ cần **3 dòng**:
    ```cypher
    MATCH path = (:Course {code: $code})-[:REQUIRES*1..]->(p:Course)
    RETURN p.code AS code, min(length(path)) AS depth
    ORDER BY depth ASC, code ASC
    ```
  - **Độ dễ đọc:** Mẫu ASCII `-[:REQUIRES*1..]->` trong Cypher thể hiện trực tiếp ý nghĩa đồ thị ("đi theo chuỗi cạnh `REQUIRES` từ 1 bước trở lên"), không cần tự viết bảng tạm đệ quy hay nối bảng trung gian như SQL.

---

### Câu 2: Ở Task 2, vì sao truy vấn chỉ trả về mỗi môn tiên quyết một lần sau khi tổng hợp? Có bao nhiêu đường đi từ `CAP401` tới `CS101`?

- **Vì sao mỗi môn tiên quyết chỉ xuất hiện đúng 1 lần:**
  Trong Cypher, khi mệnh đề `RETURN` có hàm tổng hợp (`min(length(path))`), Neo4j **tự động nhóm (`GROUP BY` ngầm định)** theo tất cả các biểu thức không tổng hợp còn lại trong `RETURN` — ở đây chính là `p.code AS code`. Nhờ đó, dù có nhiều đường đi khác nhau dẫn tới cùng một môn `p`, tất cả các đường đi đó được gom vào một nhóm duy nhất ứng với `p.code` và lấy độ dài đường đi nhỏ nhất `min(length(path))`.
- **Số đường đi từ `CAP401` tới `CS101`:**
  Khi chạy truy vấn không tổng hợp:
  ```cypher
  MATCH path = (:Course {code: "CAP401"})-[:REQUIRES*1..]->(:Course {code: "CS101"})
  RETURN [n IN nodes(path) | n.code] AS route, length(path) AS hops;
  ```
  Kết quả trả về **2 đường đi**:
  1. `["CAP401", "ML201", "CS102", "CS101"]` — độ sâu `3` bước (`hops = 3`).
  2. `["CAP401", "DB301", "DB201", "CS102", "CS101"]` — độ sâu `4` bước (`hops = 4`).
  Sau khi tổng hợp bằng `min(length(path))`, `CS101` được trả về 1 lần với `depth = min(3, 4) = 3`.

---

### Câu 3: Ở Bước 8, operator đầu tiên khi có và không có constraint là gì, và bao nhiêu `db hits`? Điều gì sẽ xảy ra với 100.000 sinh viên?

- **So sánh thực nghiệm ở Bước 8 (trên 10 sinh viên):**

  | Tiêu chí | Có constraint `student_id` | Không có constraint `student_id` |
  | :--- | :--- | :--- |
  | **Operator tìm `:Student {id: 'S01'}`** | `NodeUniqueIndexSeek` | `NodeByLabelScan` $\rightarrow$ `Filter` |
  | **`dbHits` tại bước tìm `:Student`** | **$2$** (`rows = 1`) | **$11 + 10 = 21$** (`rows = 10` $\rightarrow$ `1`) |
  | **Tổng `dbHits` toàn truy vấn** | **$237$** | **$256$** |

- **Điều gì xảy ra khi có $100.000$ sinh viên:**
  - **Không có constraint:** `NodeByLabelScan` phải quét qua toàn bộ $100.000$ node `:Student` ($\approx 100.001\text{ dbHits}$) rồi `Filter` đọc thuộc tính `id` của từng node ($\approx 100.000\text{ dbHits}$), tức tốn hơn **$200.000\text{ dbHits}$** chỉ để tìm 1 sinh viên — độ phức tạp tăng tuyến tính **$O(N)$**.
  - **Có constraint (`IS UNIQUE`):** Neo4j tự động duy trì Range/B-tree Index trên `(:Student).id`. Operator `NodeUniqueIndexSeek` nhảy thẳng tới node `'S01'` với độ phức tạp **$O(\log N)$** (chỉ tốn khoảng $3\text{–}4\text{ dbHits}$), còn phần kiểm tra 13 môn học phía sau nhờ **index-free adjacency** giữ nguyên chi phí không đổi.

---

### Câu 4: Vì sao `FRIEND` chỉ được lưu theo một chiều? Điều gì sẽ sai ở Task 4 và Task 5 nếu bạn lưu cả hai chiều mà giữ nguyên truy vấn?

- **Vì sao `FRIEND` chỉ lưu 1 chiều:**
  Trong Neo4j, mỗi relationship vật lý đều lưu con trỏ hai chiều ở tầng lưu trữ, nên việc duyệt không có mũi tên `(a)-[:FRIEND]-(b)` nhanh ngang ngửa với duyệt có mũi tên `(a)-[:FRIEND]->(b)`. Lưu 1 chiều giúp tiết kiệm một nửa dung lượng cạnh, tránh phải ghi/xoá kép và loại bỏ nguy cơ dữ liệu bất nhất (có `A -> B` nhưng quên `B -> A`).
- **Nếu lưu `FRIEND` cả hai chiều (`(a)-[:FRIEND]->(b)` VÀ `(b)-[:FRIEND]->(a)`) mà giữ nguyên truy vấn:**
  1. **Ở Task 4 (`suggest_friends`) và Task 5 (`connection`) hiện tại:**
     - Task 4 dùng `WHERE NOT (s)-[:FRIEND]-(other)` và đếm trên `:PASSED`: bản thân điều kiện phủ định `NOT (s)-[:FRIEND]-(other)` vẫn đúng, **nhưng** nếu truy vấn đếm số bạn chung `(s)-[:FRIEND]-(mf)-[:FRIEND]-(other)` mà không `DISTINCT` hoặc không định hướng thì mỗi người bạn chung sẽ bị **đếm gấp 4 lần** ($2 \times 2$ cạnh).
     - Ở Task 5 (`connection`), `shortestPath((a)-[:FRIEND*]-(b))` tìm 1 đường ngắn nhất nên độ dài không đổi, nhưng nếu dùng `MATCH (a)-[:FRIEND*1..k]-(b)` hoặc `allShortestPaths`, số lượng đường đi giữa hai sinh viên cách nhau $L$ bước sẽ **bùng nổ gấp $2^L$ lần** (vì mỗi bước nhảy có 2 cạnh song song ngược chiều nhau).

---

### Câu 5: Trường muốn lưu mọi lần học một môn (sinh viên có thể trượt và học lại, ở các học kỳ khác nhau). Hãy thiết kế lại mô hình: điểm vẫn nằm trên relationship, hay cần một node `:Enrollment`? Vẽ mô hình mới và viết lại truy vấn Task 1 cho nó.

- **Lựa chọn thiết kế:**
  Nếu một sinh viên học lại một môn ở nhiều học kỳ (kèm học kỳ `term`, năm học `year`, điểm `grade`, trạng thái `passed`, giảng viên...), thông tin lần học đã trở thành một thực thể có nhiều thuộc tính và có thể liên kết tới các node khác (như `:Semester` hoặc `:ClassSection`). Do đó, **nên tách thành node trung gian `:Enrollment`** (thay vì nhồi nhiều relationship cùng loại `PASSED`/`ATTEMPTED` giữa 2 node).

- **Sơ đồ mô hình mới:**
  ```mermaid
  flowchart LR
      S["(:Student {id, name, year})"] -->|":ENROLLED_IN"| E["(:Enrollment {term, grade, status})"]
      E -->|":FOR_COURSE"| C["(:Course {code, title, credits})"]
  ```

- **Truy vấn Task 1 viết lại trên mô hình `:Enrollment`** *(lấy điểm cao nhất của mỗi môn mà sinh viên đã qua)*:
  ```cypher
  MATCH (:Student {id: $sid})-[:ENROLLED_IN]->(e:Enrollment)-[:FOR_COURSE]->(c:Course)
  WHERE e.status = 'PASSED' OR e.grade >= 5.0
  RETURN c.code AS code, max(e.grade) AS grade
  ORDER BY grade DESC, code ASC
  ```

---

### Câu 6: Ở Task 7, điều gì sẽ sai nếu bước kiểm tra tiên quyết và bước ghi chạy trong hai lời gọi `execute_query` riêng, trong khi một chương trình khác đang xoá các relationship `PASSED` cùng lúc?

- **Hiện tượng lỗi (Race Condition / Time-Of-Check to Time-Of-Use - TOCTOU):**
  Mỗi lời gọi `driver.execute_query(...)` mở và đóng **một transaction độc lập**. Nếu tách thành 2 lần gọi:
  1. **Transaction A1 (Kiểm tra):** Kiểm tra thấy sinh viên `S01` đã có `(:Student {id:'S01'})-[:PASSED]->(:Course {code:'DB201'})` $\rightarrow$ hợp lệ để học `DB301`. Transaction A1 kết thúc.
  2. **Transaction B (Chạy đồng thời ở tiến trình khác):** Xoá relationship `PASSED` của `S01` với môn `DB201` (ví dụ do huỷ kết quả thi hoặc nhập nhầm) và commit.
  3. **Transaction A2 (Ghi):** Chạy `MERGE (s)-[:PASSED]->(:Course {code:'DB301'})` và commit thành công.
- **Hậu quả:** Cơ sở dữ liệu rơi vào trạng thái **vi phạm toàn vẹn nghiệp vụ (Write Skew / Inconsistent State)**: sinh viên `S01` được ghi nhận đã qua `DB301` trong khi môn tiên quyết bắt buộc `DB201` đã bị xoá! Khi gộp cả bước kiểm tra và bước ghi vào chung một hàm `_record_pass_tx` chạy qua `session.execute_write`, tất cả thực thi trong **cùng một ACID transaction** (và driver có thể tự động retry an toàn toàn bộ hàm nếu gặp xung đột khóa/deadlock).

---

## PHẦN 3: LỜI GIẢI CÁC BÀI TẬP CUỐI BÀI & MỞ RỘNG

Toàn bộ mã nguồn Cypher cho phần Mở rộng và 5 Bài tập cuối bài được lưu tại [exercises.cypher](file:///d:/.A-Courses/Y3/A-DB/neoj4/exercises.cypher):

1. **Bài tập 1 (Bạn của bạn của Linh ở Hà Nội):**
   ```cypher
   MATCH (linh:Person {name: "Linh"})-[:FRIEND]-(:Person)-[:FRIEND]-(fof:Person)
   WHERE fof <> linh AND NOT (linh)-[:FRIEND]-(fof) AND fof.city = "Hanoi"
   RETURN DISTINCT fof.name AS friend_of_friend, fof.city AS city;
   ```
2. **Bài tập 2 (Gợi ý sách cho Mai & Tổng chi tiêu mỗi người):**
   ```cypher
   // Gợi ý sách cho Mai
   MATCH (mai:Person {name: "Mai"})-[:FRIEND]-(friend:Person)-[:BOUGHT]->(book:Book)
   WHERE NOT (mai)-[:BOUGHT]->(book)
   RETURN book.title AS recommended_book, count(DISTINCT friend) AS friend_buyers
   ORDER BY friend_buyers DESC, recommended_book ASC;

   // Tổng số tiền mỗi người đã chi
   MATCH (p:Person)
   OPTIONAL MATCH (p)-[r:BOUGHT]->(b:Book)
   RETURN p.name AS person, coalesce(sum(coalesce(r.pricePaid, b.price)), 0) AS total_spent
   ORDER BY total_spent DESC, person ASC;
   ```
3. **Bài tập 3 (Mạng Metro `:Station` và `:NEXT`):**
   ```cypher
   MATCH (start:Station {name: "Cat Linh"}), (dest:Station {name: "Ha Dong"}),
         path = shortestPath((start)-[:NEXT*]-(dest))
   RETURN [s IN nodes(path) | s.name] AS stations,
          length(path) AS stops,
          reduce(total = 0, r IN relationships(path) | total + r.minutes) AS total_minutes;
   ```
4. **Bài tập 4 (So sánh 2 cách mô hình hoá lịch sử làm việc):**
   - **Cách 1 (Property trên relationship `(:Person)-[:WORKED_AT {role, startDate, endDate}]->(:Company)`):** Gọn nhẹ, trả lời rất nhanh câu hỏi *"Ai đã từng làm ở công ty X?"* chỉ bằng 1 bước nhảy. Tuy nhiên không thể gắn thêm relationship từ vị trí công việc đó sang thực thể khác (như `:Project`, `:Department`, `:Skill`).
   - **Cách 2 (Node trung gian `(:Person)-[:HELD]->(:Position)-[:AT]->(:Company)`):** Trả lời dễ dàng các câu hỏi phức tạp như *"Trong thời gian giữ chức vụ Data Engineer tại FPT, Linh đã tham gia những dự án `:Project` nào và quản lý những ai?"*.
5. **Bài tập 5 (`PROFILE` trước và sau khi tạo Uniqueness Constraint cho `:Person {name: "Linh"}`):**
   - Trước khi có constraint: dùng `NodeByLabelScan` + `Filter` (quét toàn bộ các node `:Person`).
   - Sau khi `CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE`: dùng `NodeUniqueIndexSeek` tra cứu trực tiếp qua index với `dbHits = 2`.
