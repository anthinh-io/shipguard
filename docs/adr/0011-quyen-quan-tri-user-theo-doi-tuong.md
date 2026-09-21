# ADR-0011: Quyền quản trị `User` phân theo đối tượng bị tác động

**Trạng thái:** Đã chấp nhận
**Ngày:** 2026-09-21
**Người quyết định:** Chủ dự án

## Bối cảnh

Từ ADR-0006, mọi thao tác quản trị `User` đi qua một cổng kiểm tra duy nhất: người gọi
phải mang vai trò `Logistics Manager` hoặc `Super Admin`. Qua được cổng đó rồi thì cả
bốn thao tác — tạo tài khoản, khóa/mở khóa, đặt lại mật khẩu, đổi vai trò — đều mở như
nhau. Nói cách khác, hai vai trò này đang có quyền y hệt nhau; khác biệt duy nhất là
không ai chạm được vào `Super Admin`.

Điều đó nghĩa là một `Logistics Manager` tự nâng được một đồng nghiệp lên ngang hàng
mình, đặt lại được mật khẩu của một `Logistics Manager` khác rồi đăng nhập bằng tài
khoản đó, hoặc khóa chính người đã cấp tài khoản cho mình. Ở quy mô vài người dùng nội
bộ thì chưa ai gặp sự cố, nhưng đây là thứ không giải thích được khi có người hỏi "ai
kiểm soát ai".

Các lực tác động:

- **`Logistics Manager` là người quản lý trực tiếp đội `Operations Staff`** — nhận người
  mới, cho người cũ nghỉ, xử lý khi nhân viên quên mật khẩu.
- **Đổi vai trò khác bản chất với ba thao tác còn lại**: nó thay đổi chính tập người có
  quyền quản trị, chứ không chỉ tác động lên một tài khoản.
- **Chỉ có đúng một `Super Admin`**, sinh từ cấu hình lúc cài đặt, không gán được qua API
  (ADR-0006 mục 6), và được một chỉ mục duy nhất trong cơ sở dữ liệu bảo đảm.
- **Không có dịch vụ email** (ADR-0006), nên đặt lại mật khẩu bằng tay là đường duy nhất
  khi một `User` quên mật khẩu.

## Quyết định

Quyền quản trị phân theo **đối tượng bị tác động**, không theo loại thao tác. Diễn đạt
bằng một câu: *`Logistics Manager` quản trị `Operations Staff`; `Super Admin` quản trị
tất cả.*

| Thao tác | LM → OS | LM → LM | LM → SA | SA → OS | SA → LM | SA → SA |
| --- | --- | --- | --- | --- | --- | --- |
| Tạo tài khoản | Có | Không | Không | Có | Có | Không |
| Khóa / mở khóa | Có | Không | Không | Có | Có | Không |
| Đặt lại mật khẩu | Có | Không | Không | Có | Có | Không |
| Đổi vai trò | Không | Không | Không | Có | Có | Không |

Cột "Tạo tài khoản" đọc theo vai trò của tài khoản sắp được tạo.

1. **`Logistics Manager` chỉ tác động được lên `User` có vai trò `operations_staff`.**
   Đây là cách phát biểu chuẩn của luật; mục Hệ quả giải thích vì sao phải giữ đúng cách
   phát biểu này chứ không phải một cách tương đương gần đúng.
2. **Đổi vai trò là đặc quyền riêng của `Super Admin`**, kể cả khi đối tượng là
   `Operations Staff`: nâng một `Operations Staff` lên `Logistics Manager` là mở rộng
   tập người quản trị, vượt khỏi phạm vi "chỉ chạm `Operations Staff`".
3. **Vẫn đúng một `Super Admin`.** Quên mật khẩu thì người có quyền vào máy chủ chạy
   script CLI để đặt lại (ADR-0006 mục 6).
4. **`GET /users` giữ nguyên**: ai qua được cổng quản trị đều thấy toàn bộ danh sách.
   Nhìn thấy khác với sửa được — `Logistics Manager` cần biết ai đang có trong hệ thống
   để không tạo trùng người và để biết cần nhờ ai khi gặp việc ngoài quyền.
5. **Giao diện ẩn thao tác** ở những dòng người đang đăng nhập không quản trị được, đúng
   cách dòng `Super Admin` đang hiển thị hôm nay.
6. **API trả lỗi riêng cho từng lý do**: chạm `Super Admin` giữ nguyên thông điệp cũ;
   chạm một `Logistics Manager` khác nhận một lỗi 403 nói rõ chỉ `Super Admin` làm được
   việc đó, để người gọi thẳng API biết bước tiếp theo.
7. **Bỏ rào "không ai tự quản lý chính mình"** — xem mục Hệ quả.

## Các phương án đã cân nhắc

### Phương án A: Giữ nguyên — hai vai trò quyền ngang nhau

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp — một cổng kiểm tra một chiều |
| Số câu để diễn đạt luật | Một — "qua được cổng thì làm được mọi thứ trừ Super Admin" |
| Nguy cơ tự nâng quyền | Có — LM nâng được người khác lên ngang mình |
| Nút thắt vận hành | Không — LM xử lý được mọi việc của đội |
| Công sức | Không có |

**Ưu:** không phải làm gì; cổng kiểm tra đơn giản nhất có thể.
**Nhược:** không trả lời được câu "ai kiểm soát ai"; ranh giới giữa hai vai trò chỉ tồn
tại trên giấy.

### Phương án B: Phân theo loại thao tác

Đặt lại mật khẩu và đổi vai trò là việc riêng của `Super Admin`, bất kể đối tượng là ai.
`Logistics Manager` chỉ tạo và khóa.

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — kiểm hai chiều: loại thao tác và đối tượng |
| Số câu để diễn đạt luật | Hai — một câu cho thao tác, một câu cho đối tượng |
| Nguy cơ tự nâng quyền | Không |
| Nút thắt vận hành | Có — mọi lần quên mật khẩu đều chờ đúng một người |
| Công sức | Tương đương phương án C |

**Ưu:** đặt lại mật khẩu — thao tác chiếm được tài khoản người khác — nằm trong tay một
người duy nhất.
**Nhược:** `Logistics Manager` quản lý đội `Operations Staff` nhưng không tự gỡ được việc
thường gặp nhất của đội mình; luật cần hai chiều để diễn đạt nên khó nhớ hơn.

### Phương án C: Phân theo đối tượng bị tác động

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — kiểm theo cặp (vai trò người gọi × vai trò đối tượng) |
| Số câu để diễn đạt luật | Một — "LM quản trị OS; SA quản trị tất cả" |
| Nguy cơ tự nâng quyền | Không — đổi vai trò nằm ngoài tầm với của LM |
| Nút thắt vận hành | Nhỏ — chỉ việc đổi vai trò mới cần `Super Admin` |
| Công sức | Kiểm theo cặp ở tầng dịch vụ; `AssignableRole` hết tự diễn đạt được luật |

**Ưu:** một câu là đủ diễn đạt; khớp với cách đội thật sự vận hành — cấp trên trực tiếp
lo cho cấp dưới trực tiếp.
**Nhược:** phải kiểm theo cặp thay vì kiểm một chiều; luật rời khỏi kiểu dữ liệu nên
người đọc kiểu dữ liệu không còn thấy hết luật.

## Phân tích đánh đổi

A rụng vì nó chính là vấn đề cần sửa.

Đánh đổi thật nằm giữa B và C, và hai phương án này chỉ lệch nhau **đúng một ô**: có cho
`Logistics Manager` đặt lại mật khẩu của `Operations Staff` hay không.

B coi đặt lại mật khẩu là thao tác chiếm được tài khoản người khác nên phải dồn về một
người. Lập luận đó đúng khi đối tượng ngang hàng hoặc cao hơn, nhưng mờ đi khi đối tượng
là `Operations Staff`: `Logistics Manager` vốn đã tạo được và khóa được tài khoản đó, nên
thêm quyền đặt lại mật khẩu gần như không mở rộng thứ họ đã làm được với đội mình. Đổi
lại, vì không có dịch vụ email nên đặt lại mật khẩu bằng tay là đường duy nhất khi nhân
viên quên mật khẩu — dưới B, mọi lần quên mật khẩu trong toàn hệ thống đều xếp hàng chờ
đúng một người.

Chọn C. Cái giá của C — phần kiểm quyền phức tạp hơn một chút và phải rời khỏi kiểu dữ
liệu — rẻ hơn nhiều so với một nút thắt vận hành gặp hằng tuần.

## Hệ quả

- **Dễ hơn:** luật diễn đạt bằng một câu, nên giải thích cho người dùng mới và viết thành
  test đều ngắn. Ranh giới giữa `Logistics Manager` và `Super Admin` trở thành thật chứ
  không chỉ nằm trên tài liệu.
- **Khó hơn — kiểu dữ liệu không còn là toàn bộ luật.** `AssignableRole` là một `Literal`
  dùng chung cho cả đường tạo tài khoản lẫn đường đổi vai trò, và được kiểm trước khi
  biết người gọi là ai. Dưới quyết định này, tập vai trò hợp lệ phụ thuộc vào vai trò
  người gọi, nên phần kiểm phải nằm ở tầng dịch vụ, cạnh định danh người gọi. Người đọc
  `AssignableRole` mà tưởng đó là toàn bộ luật sẽ hiểu sai.
- **Khó hơn — đường tạo tài khoản cần đường kiểm riêng.** Ba thao tác còn lại đều đi qua
  cùng một chỗ nạp đối tượng, nên gắn luật vào đó là đủ. Tạo tài khoản thì chưa có đối
  tượng để nạp, nên nó phải tự kiểm vai trò sắp gán theo vai trò người gọi.
- **Vai trò người gọi đọc từ token.** Cổng quản trị hiện đã đọc vai trò từ access token,
  và ADR-0006 đã chấp nhận sẵn việc vai trò đó cũ tối đa 15 phút. Luật mới dùng cùng
  nguồn, nên không mở thêm khoảng lệch nào ngoài khoảng đã chấp nhận.
- **Rào "không ai tự quản lý chính mình" bị bỏ, và việc bỏ nó dựa vào đúng một cách phát
  biểu.** Dưới luật mới, người thao tác chỉ có thể là `Logistics Manager` hoặc
  `Super Admin`: người thứ nhất chạm chính mình là chạm một `logistics_manager` nên bị
  luật mới chặn, người thứ hai bị rào `Super Admin` chặn. Rào cũ không còn đường chạy
  tới. Nhưng điều đó chỉ đúng khi luật được phát biểu là *"`Logistics Manager` chỉ tác
  động được lên `operations_staff`"*. Nếu ai đó sau này nới thành *"`Logistics Manager`
  không tác động được lên `Logistics Manager` khác ngoài chính mình"* — một cách nới nghe
  rất tự nhiên — thì lỗ hổng tự quản lý mở lại mà không có bài test nào đỏ.
- **Vài bài test hiện có dùng thao tác quản trị chỉ để dựng cảnh**, không phải để kiểm
  quyền. Chúng đều là `Logistics Manager` khóa một `Operations Staff` nên vẫn hợp lệ,
  nhưng sẽ vỡ theo nếu chữ ký hàm quản trị đổi để nhận thêm vai trò người gọi.
- **Thông điệp lỗi mới chỉ người gọi thẳng API mới thấy.** Vì giao diện ẩn hẳn thao tác
  không dùng được, và lớp gọi API phía trình duyệt gộp mọi thất bại thành một thông báo
  chung, lỗi 403 phân biệt lý do là để phục vụ người gọi API trực tiếp. Muốn giao diện
  hiển thị đúng lý do thì phải tách mã lỗi ở lớp gọi API — không nằm trong quyết định này.
- **Giới hạn đã chấp nhận:** đổi vai trò dồn vào một người duy nhất. Người đó nghỉ thì
  không ai nâng hay hạ vai trò được cho tới khi họ quay lại.
- **Không cần di trú dữ liệu.** Đây là thay đổi luật, không phải thay đổi dữ liệu. Những
  `Logistics Manager` đang có sẽ mất bớt quyền ngay khi bản mới chạy; không có thao tác
  nào đang dở dang để phải báo trước.
- **Cần xem lại:** nếu đội lớn tới mức chờ `Super Admin` thành nút thắt thật, mở lại
  chuyện cho phép nhiều `Super Admin` — kéo theo phải sửa định nghĩa ở `CONTEXT.md`, mở
  `AssignableRole`, gỡ chỉ mục duy nhất trong cơ sở dữ liệu, và dựng rào để `Super Admin`
  cuối cùng không bị ai hạ xuống.

## Việc cần làm

1. [x] Kiểm quyền theo cặp (vai trò người gọi × vai trò đối tượng) ở tầng dịch vụ, dùng
   chung cho khóa/mở khóa, đổi vai trò và đặt lại mật khẩu
2. [x] Đường kiểm riêng cho việc tạo tài khoản, theo vai trò người gọi
3. [ ] Chặn đổi vai trò với người gọi không phải `Super Admin`
4. [x] Bỏ rào "không ai tự quản lý chính mình" cùng các bài test khẳng định nó
5. [x] Lỗi 403 mới cho trường hợp chạm một `Logistics Manager` khác — chỉ phục vụ người
   gọi API trực tiếp, không đổi lớp gọi API phía trình duyệt
6. [x] Giao diện ẩn thao tác theo vai trò người đang đăng nhập, cả ở bảng lẫn ở hộp thoại
   tạo tài khoản
7. [ ] Cập nhật test backend và test đầu-cuối theo ma trận quyền mới
