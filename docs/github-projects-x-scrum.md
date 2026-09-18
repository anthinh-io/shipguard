# Cẩm nang: GitHub Projects x Scrum

Nguồn: "Scrum with GitHub Projects" (Benjamin Day, Professional Scrum Trainer — scrum.org).

## 1. Project Fields 

| Field | Loại | Mục đích |
| --- | --- | --- |
| `Item type` | Single-select (`User Story`, `Task`) | Phân biệt PBI/Story với Sub-Task |
| `Status` | Single-select (`To do`, `In progress`, `Done`) | Trạng thái công việc |
| `Estimate` | Number | Story point (Fibonacci) cho Story; **số giờ còn lại** cho Task. Không dùng field `Size` dựng sẵn — không hữu ích cho Scrum |
| `Iteration` | Iteration (built-in) | Gán Story/Task vào đúng sprint, có sẵn start/end date |

## 2. Product Backlog

- Đổi layout view sang **Table** (không dùng board mặc định) để xem dạng danh sách.
- Thêm item mới bằng phím tắt `Ctrl+Space` hoặc nút `+`.
- ⚠️ Nếu gõ tiêu đề trực tiếp ở cuối bảng, item tạo ra là **Draft issue** (bản nháp, chưa thật) — phải bấm **Convert to issue** và chọn đúng repo để thành Issue chính thức.
- Đặt `Item type = User Story` cho mọi item trong backlog.
- **Sắp ưu tiên bằng kéo-thả** — dòng trên cùng = ưu tiên cao nhất. Không cần con số phức tạp.
- View "Product Backlog" nên lọc `Item type: User Story` + **chưa gán Iteration**, để không lẫn với các story đã vào sprint.
- Dùng **Slice by → Item type** để xem tổng Story Points (field Estimate) của toàn backlog.

## 3. Sprint Planning

**Pha 1 — "Làm gì" (What):** chọn story ưu tiên cao nhất từ backlog, gán `Iteration` = sprint sắp tới (cột Iteration có sẵn ngay trong view Table, chỉ cần click dropdown). Muốn gán hàng loạt: chọn nhiều dòng rồi dùng **fill-down** (kéo dấu `+` ở góc ô).

**Pha 2 — "Làm sao" (How):** với mỗi story đã chọn:

1. Mở story, bấm **Create sub-issue**.
2. Nhập Title + Description cho Task.
3. Đặt `Item type = Task`.
4. **Bắt buộc chọn đúng Project** ở trường Project — mặc định GitHub chỉ tạo issue ở repo, không tự thêm vào Project.
5. Tick **"Create more sub-issues"** nếu còn task khác cần tạo cho story này — giúp giữ nguyên Item type/Project đã chọn, tạo nhanh liên tiếp.
6. Gán `Estimate` (số giờ) cho từng task.

## 4. Cạm bẫy: Sub-issue "biến mất" khỏi view Sprint

**Nguyên nhân:** Task con **không tự động thừa hưởng** giá trị `Iteration` của story cha. Nếu view Sprint đang lọc theo `iteration:@current`, các task vừa tạo (Iteration đang trống) sẽ **không hiển thị** — trông như bug nhưng thực chất là quên gán.

**Cách khắc phục:**

1. Tạo 1 view Table tạm, filter `Item type: Task`.
2. Thêm cột `Parent issue` và `Iteration` để dễ nhìn.
3. Gán `Iteration` đúng sprint cho các task đang trống, dùng fill-down để áp hàng loạt.
4. Quay lại view Sprint — task giờ đã hiển thị đầy đủ.

## 5. Check-in hằng ngày (thay Daily Scrum)

Mở view **Current Iteration**, tự hỏi: _đang thế nào? có đạt kế hoạch không? có gì cản trở?_

- **Slice by Task** (góc nhìn kỹ thuật): kéo card qua `To do → In progress → Done`. Mỗi ngày mở task đang làm, **tự sửa `Estimate` = số giờ còn lại** (KHÔNG tự động cập nhật). Khi xong, kéo sang `Done` **và tự set Estimate = 0** (GitHub không tự xóa giá trị này).
- **Slice by User Story** (góc nhìn tổng thể): xem `Sub-issues progress` (% task con đã Done). Khi 100% → kéo story sang `Done`.
- **Velocity** = tổng `Estimate` (story points) của các story đã ở cột `Done` trong sprint.

## 6. Reporting & Charts (Insights → Charts)

| Biểu đồ | Layout | Cấu hình |
| --- | --- | --- |
| Burndown Task | Line | y = Sum(Estimate), filter `Item type: Task`, scope current iteration — lý tưởng dốc về 0 cuối sprint |
| Story Status | Column | x = Status, group by Item type, filter `iteration:@current` + `Item type: User Story` |
| Task Remaining Hours by Status | Column | y = Sum(Estimate), filter `Item type: Task` |
