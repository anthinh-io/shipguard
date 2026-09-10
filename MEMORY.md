# MEMORY.md

- Người dùng quản lý dự án theo phương pháp Agile/Scrum — ưu tiên cách phản hồi giúp họ tự tư duy trước khi thấy đáp án, thay vì làm hộ toàn bộ.
- Tài liệu dự án dùng tiếng Việt là ngôn ngữ chính; giữ tên riêng công nghệ nguyên bản (React, FastAPI, XGBoost, API, REST...) khi không có thuật ngữ tương đương tự nhiên.
- Với nội dung có cấu trúc (tài liệu, kế hoạch...), người dùng muốn thấy nội dung dự kiến đầy đủ của từng tệp ngay trong kế hoạch — không chỉ danh sách tiêu đề — để duyệt trước khi tệp được viết ra.
- Các thay đổi hiển thị công khai trên GitHub (Issue, Project, Label, Milestone, Pull Request...) nên được xác nhận lặp lại trước mỗi lần thao tác — vì khó hoàn tác và ảnh hưởng đến thứ người khác nhìn thấy.
- Commit message không cần trailer đồng tác giả (Co-Authored-By), viết bằng tiếng Anh, kể cả khi UI/tài liệu miền là ngôn ngữ khác — kiểm tra `git log` trước khi viết commit nếu chưa chắc.
- Repo thuộc tài khoản cá nhân (User), không phải Organization — field "Issue type" dựng sẵn của GitHub không khả dụng ở đây; dùng field `Item type` (User Story/Task) trong GitHub Project để thay thế.
- GitHub Projects v2 dùng API/scope quyền riêng, tách biệt với quyền truy cập Issues/PR thông thường — đừng giả định token đã có đủ quyền, hãy tự xác minh trước khi thao tác.
- Đặt Status = Done trên GitHub Project sẽ tự động đóng Issue liên kết.
- Tiêu chí chấp nhận viết bằng văn phong tự nhiên, không thuật ngữ kỹ thuật, kể cả với dữ liệu/mô hình; ưu tiên Given-When-Then hơn Checklist khi cần dễ hình dung kịch bản cho nhiều vai trò đọc.
- Trong `CONTEXT.md`, tên thuật ngữ viết tiếng Anh để khớp định danh trong code, còn định nghĩa viết tiếng Việt — tránh phải dịch qua lại mỗi lần viết code hay test.
