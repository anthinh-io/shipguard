# Cẩm nang: Mô hình quản lý dự án Agile cho dự án cá nhân

Tài liệu này lưu lại phần thảo luận về phương pháp làm việc, để đọc lại khi cần nhắc lại cách tư duy phân rã công việc.

## 1. Mô hình Agile rút gọn kiểu Kanban-in-Sprint

Dự án do **1 thành viên** thực hiện, nên không cần đủ vai trò Scrum (Product Owner / Scrum Master / Dev Team) và không cần các nghi thức dành cho nhóm (daily standup meeting, sprint planning poker...).

Vẫn giữ lại phần cốt lõi giúp Agile hiệu quả:

- **Nhịp sprint cố định (1 tuần)** — ép tiến độ, phát hiện rủi ro sớm thay vì dồn việc đến gần deadline.
- **Sprint Goal rõ ràng** — mỗi tuần có một mục tiêu có thể tự kiểm chứng, thay vì mốc giai đoạn mơ hồ kéo dài 3-4 tuần.
- **Mỗi Sprint giao một lát cắt xuyên suốt (vertical slice)** — làm đủ từ dữ liệu đến model, API, UI ở mức tối thiểu trong cùng một vòng lặp phát triển, thay vì làm xong hẳn một tầng rồi mới chuyển sang tầng khác. Nhờ vậy sau mỗi sprint đều có một thứ dùng được, dù còn thô, không phải chờ đến gần cuối dự án mới thấy giá trị.
- **Tài liệu kế hoạch mô tả hiện tại** — ghi mục tiêu đang có hiệu lực, không thuật lại lịch sử điều chỉnh (việc đó đã có trong commit/PR/Issue).

## 2. Cấu trúc công việc

```
Epic (mục tiêu lớn, kéo dài nhiều vòng lặp phát triển)
 └── User Story (một lát cắt giá trị, hoàn thành trong một sprint)
      └── Task (việc kỹ thuật cụ thể để hoàn thành story, vài giờ)
```

- **Epic** — quá lớn để làm trong một sprint, không tự kiểm chứng được ngay.
- **User Story** — một đơn vị giá trị nhỏ, có thể trình diễn/kiểm chứng độc lập. Viết theo mẫu:
  > _Là [vai trò], tôi muốn [làm được gì], để [đạt giá trị gì]._
- **Task** — bước kỹ thuật để hoàn thành một story, không cần viết theo mẫu vai trò.

## 3. Nguyên tắc INVEST — kiểm tra một story có tốt không?

| Chữ cái | Ý nghĩa | Câu hỏi tự kiểm tra |
| --- | --- | --- |
| I | Independent | Story có phụ thuộc cứng vào story khác không? |
| N | Negotiable | Story có đang mô tả "làm gì" hay đã lỡ chốt cứng "làm bằng cách nào" không? |
| V | Valuable | Story có mang lại giá trị rõ ràng (kể cả để chính mình kiểm chứng) không? |
| E | Estimable | Có ước lượng được công sức cần bỏ ra không? |
| S | Small | Có làm xong trong một sprint (1 tuần) không? |
| T | Testable | Có tiêu chí chấp nhận (Acceptance Criteria) rõ ràng để biết khi nào xong không? |

## 4. Ví dụ áp dụng: phân rã theo vertical slice

Sprint goal: _"Có một luồng dự đoán chạy được từ đầu đến cuối — nhập thông tin đơn hàng trên web, nhận lại kết quả rủi ro giao trễ"_. Đây là một lát cắt xuyên suốt: đủ dữ liệu để train, một model thật, một API, một trang web gọi API đó — nhưng phạm vi mỗi phần đều thu hẹp tối đa để vừa một sprint.

**Story 1.1** — _Là người phát triển, tôi muốn có một dataset đã xử lý tối thiểu (join, gắn nhãn is_delayed), để có đầu vào train model._

- Tiêu chí chấp nhận: dataset có nhãn `is_delayed`, không còn giá trị thiếu ở các cột dùng làm đặc trưng, đã chia train/test.

**Story 1.2** — _Là người phát triển, tôi muốn huấn luyện một model dự đoán rủi ro giao trễ với ngưỡng phân loại đã cân nhắc, và đóng gói thành REST API, để có một nguồn dự đoán thật cho web gọi tới._

- Tiêu chí chấp nhận: `POST /predict` trả về nhãn dự đoán kèm xác suất; ngưỡng phân loại được chọn có ghi lý do (không phải mặc định 0.5); F1 trên lớp trễ khác 0 khi thử với vài đơn mẫu.

**Story 1.3** — _Là người quản lý vận hành, tôi muốn nhập thông tin một đơn hàng trên web và nhận kết quả dự đoán rủi ro trễ, để thấy được luồng sản phẩm hoạt động thật._

- Tiêu chí chấp nhận (Given–When–Then):
  - **Given** API dự đoán đã sẵn sàng
  - **When** tôi nhập thông tin đơn hàng vào một biểu mẫu đơn giản trên web
  - **Then** hệ thống gọi API thật và hiển thị kết quả trong vài giây

→ 3 story thuộc 3 epic khác nhau (data, ml, dashboard) nhưng cùng phục vụ một mục tiêu sprint xuyên suốt — khác với cách phân rã theo giai đoạn.

## 5. Định nghĩa hoàn thành (Definition of Done)

- [ ] Code/chức năng chạy được, không lỗi khi thực thi thử
- [ ] Không có rò rỉ dữ liệu (data leakage) đối với các task liên quan đến mô hình học máy
- [ ] Đã commit/tạo Pull Request tương ứng
- [ ] Tự đánh giá lại Sprint Goal (đạt/chưa đạt) và ghi chú điều chỉnh cho sprint sau

## 6. Tiêu chí chấp nhận (Acceptance Criteria): Checklist hay Given–When–Then?

### 6.1 So sánh theo nhiều khía cạnh

**1. Bản chất ngôn ngữ**

- Checklist: danh sách kết quả cần đạt, không ép thứ tự logic — trả lời câu hỏi "làm xong chưa".
- Given–When–Then: xuất phát từ BDD (Behavior-Driven Development), mô tả hành vi hệ thống theo cấu trúc tiền đề → hành động → kết quả — trả lời câu hỏi "hệ thống phản ứng đúng khi nào".

**2. Độ rõ ràng về ngữ cảnh & phụ thuộc**

- GWT buộc phải nêu `Given`, tự động lộ ra phụ thuộc giữa các story (VD story sau phải `Given` kết quả của story trước).
- Checklist thường chỉ liệt kê kết quả cuối, dễ bỏ sót tiền đề ngầm định — đọc lại sau vài tuần dễ không biết cần gì trước khi kiểm tra được mục đó.

**3. Khả năng chuyển thành test tự động**

- GWT ánh xạ gần 1-1 sang khung BDD (Cucumber, pytest-bdd, Gherkin) — có thể tái dùng gần như nguyên văn làm test tự động.
- Checklist là câu tự nhiên, muốn tự động hóa phải diễn giải lại thành test, tốn thêm một bước chuyển đổi.
- Với story dạng đo đạc/khám phá dữ liệu (kiểm bằng cách đọc số liệu trong notebook, không phải test tự động), lợi thế này của GWT không phát huy tác dụng.

**4. Tương thích với tính năng có sẵn của GitHub**

- Checklist (`- [ ]`) được GitHub render thành checkbox tương tác, tự tính progress bar "x/y completed" — là input cho field Sub-issues progress dùng trong check-in hằng ngày (mục 6).
- GWT ở dạng văn xuôi không tự có checkbox — muốn giữ cả hai lợi ích phải viết dạng lai (checklist lồng GWT trong từng dòng, như ví dụ ở 8.3).

**5. Độ phù hợp theo loại story (khác biệt lớn nhất, đáng cân nhắc nhất)**

- Story có "người dùng/client thao tác → hệ thống phản hồi" (API, giao diện, e2e) → GWT tự nhiên: có actor, có action, có phản hồi rõ ràng.
- Story dạng "đo đạc/xác nhận một sự thật" (tải dữ liệu, kiểm tra chất lượng, huấn luyện mô hình) → ép vào GWT thường gượng ép, các câu `When` dễ na ná nhau ("khi tôi chạy notebook/script") vì đây là một phép đo, không phải hành vi hệ thống phản ứng với người dùng.

**6. Chi phí viết & bảo trì**

- Checklist: nhanh viết, linh hoạt, không có chi phí cú pháp.
- GWT: tốn thời gian hơn, nhưng đổi lại buộc nghĩ kỹ điều kiện đầu vào — với story mơ hồ là lợi ích thật, với story đơn giản là overhead thừa (độ phức tạp cú pháp vượt quá độ phức tạp công việc).

**7. Giá trị học tập**

- GWT là kỹ năng chuyển giao được sang viết test/BDD chuyên nghiệp sau này, luyện tư duy "hình dung kịch bản kiểm chứng trước khi code".
- Checklist là kỹ năng chốt DoD, đơn giản, thực dụng, ít học được thêm gì mới nếu đã quen.

### 6.2 Quy tắc chọn nhanh

- Story kiểu đo đạc/xác nhận dữ liệu, số liệu, mô hình → **Checklist**.
- Story kiểu người dùng/client thao tác rồi hệ thống phản hồi → **Given–When–Then**.
- Phân vân → mặc định Checklist, chỉ đổi sang GWT khi AC có nhiều hơn 1 kịch bản hành vi rõ rệt cần phân biệt.

### 6.3 Ví dụ áp dụng

**Story "kiểm tra chất lượng dữ liệu thô" → Checklist**

> Là người phát triển, tôi muốn kiểm tra chất lượng dữ liệu thô (null, trùng lặp, kiểu dữ liệu sai), để tránh lỗi ở bước phân tích sâu.
>
> - [ ] Notebook liệt kê % giá trị thiếu theo từng cột của các bảng chính
> - [ ] Ghi nhận số dòng trùng lặp và các cột sai kiểu dữ liệu (nếu có)

Đây là việc đo đạc một sự thật có sẵn trong dữ liệu, không có "người dùng thao tác lên hệ thống" — ép vào GWT sẽ ra một câu `When` gượng ép kiểu "When tôi chạy notebook", không mô tả hành vi thật nào cả.

**Story "nhập đơn hàng nhận dự đoán rủi ro trễ thời gian thực" → Given–When–Then**

> Là người quản lý vận hành, tôi muốn nhập thông tin đơn hàng trên web và nhận dự đoán rủi ro trễ thời gian thực, để chủ động xử lý rủi ro thay vì phản ứng sau khi trễ.
>
> - **Given** API dự đoán đã sẵn sàng và giao diện đã có
> - **When** tôi nhập thông tin đơn hàng vào biểu mẫu dự đoán trên web
> - **Then** hệ thống gọi API thật và hiển thị kết quả trong vài giây

Đây là hành vi hệ thống thật: có actor (người quản lý vận hành), có action rõ ràng (nhập biểu mẫu), có phản hồi rõ ràng (kết quả hiển thị). Nếu viết bằng checklist thuần, sẽ mất luôn thông tin "ai thao tác, thao tác gì" — chỉ còn lại "có kết quả", làm khó hình dung lại kịch bản khi đọc lại sau này hoặc khi chuyển thành test e2e.

## 7. Tài liệu tham khảo: Sprint Retrospective

Mặc định dùng Issue riêng "Iteration N — Retrospective", theo outline:

1. **Sprint Goal & mức đạt được** — trả lời câu hỏi "sprint này có làm đúng thứ đã hứa không", tách bạch khỏi số lượng ticket (hoàn thành nhiều ticket không đồng nghĩa đạt goal — số đó thuộc mục 2).
2. **Sprint Review** — bằng chứng cụ thể đã hoàn thành/thử nghiệm được, làm căn cứ cho nhận định đạt/chưa đạt ở mục 1 — để người đọc lại hình dung được sản phẩm thật đã thay đổi thế nào, không chỉ đọc danh sách ticket.
3. **Retrospective: Làm tốt / Cần điều chỉnh** — tách riêng cái nên giữ khỏi cái cần sửa, để mục 5 (action item) bắt nguồn rõ ràng từ đây thay vì lẫn lộn giữa khen và phê bình.
4. **Carryover** — ghi nhận trung thực việc chưa xong, tránh việc dở dang âm thầm biến mất khỏi tầm nhìn khi đóng sprint. Bỏ qua nếu sprint đóng tròn.
5. **Action item cho sprint sau** — biến nhận định ở mục 3/4 thành việc làm cụ thể, kiểm tra được (checkbox `- [ ]`) — không có mục này, retro chỉ dừng ở nhận xét, không tạo ra thay đổi hành vi thật.
6. **Liên kết** — trỏ tới bằng chứng/tài liệu chi tiết hơn (PR, Issue...) khi cần, giữ nội dung Issue chính ngắn gọn mà vẫn truy được gốc. Bỏ qua nếu không có.
