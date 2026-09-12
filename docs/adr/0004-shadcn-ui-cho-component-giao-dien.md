# ADR-0004: Dùng shadcn/ui trên nền Radix cho component giao diện

**Trạng thái:** Đã chấp nhận
**Ngày:** 2026-09-12
**Người quyết định:** Chủ dự án

## Bối cảnh

ADR-0003 chọn Tailwind CSS v4 làm hệ thống style và để ngỏ một điều kiện: _"nếu dự án về sau lấy một bộ component dựng sẵn có hệ thống style riêng, hai bên sẽ chồng nhau và cần chọn lại."_ Điều kiện đó vừa tới.

Bảng điều khiển ở #6 là màn hình thật đầu tiên và nó đơn giản: một đầu trang, một dòng kỳ báo cáo, hai ô KPI. Toàn bộ dựng được bằng lớp tiện ích Tailwind thuần, không cần hành vi tương tác nào.

Các ticket giao diện còn lại thì khác hẳn. #11 cần bộ chọn khoảng ngày và bộ chọn bang. #12 cần ô gợi ý gõ dần nhiều cột, có điều hướng bàn phím theo chuẩn ARIA combobox. #9 và #10 cần biểu đồ. #13 cần bộ chọn chế độ so sánh. Đây không còn là bài toán bố cục nữa mà là bài toán hành vi: bẫy tiêu điểm, định vị lớp nổi, quản lý `aria-activedescendant`, đóng khi bấm ra ngoài, khoá cuộn nền. Tự viết những thứ này đúng chuẩn là việc nhiều tuần, và không có phần nào trong đó là giá trị riêng của ShipGuard.

Hai lực định hình thời điểm:

- **Đợt chuyển đổi rẻ nhất là bây giờ.** Phần tốn kém của việc nhận shadcn không phải các component mà là bộ token màu và cơ chế chế độ tối — hai thứ chạm vào mọi giao diện đã dựng. Hôm nay "mọi giao diện đã dựng" là một component 150 dòng. Tới #11 thì là thanh bộ lọc, hai biểu đồ và sáu ô KPI. Cùng lập luận mà #7 dùng để đặt phần song ngữ lên sớm.
- **Chưa có bề mặt style nào đáng để phải tôn trọng.** `globals.css` mới có bốn biến màu và hai khối media query.

Ràng buộc từ `CLAUDE.md` §2: không dựng thứ chưa ai yêu cầu. Nhận cả một hệ component ở thời điểm chỉ mới cần một cái thẻ là vượt phạm vi hẹp của một ticket bảng điều khiển.

## Quyết định

Nhận **shadcn/ui** làm nguồn component giao diện, khởi tạo với `style` là **`radix-nova`** — tức thư viện nền **Radix**, không phải mặc định Base UI hiện hành của CLI.

Ba hệ quả cấu hình đi kèm:

1. **Alias giữ mọi thứ dưới `app/`**: `components` = `@/app/components`, `ui` = `@/app/components/ui`, `lib` = `@/app/lib`, `utils` = `@/app/lib/utils`, `hooks` = `@/app/hooks`. Không có thư mục gốc song song nào sinh ra bên cạnh `app/components/` đã có.
2. **Chế độ tối chuyển từ `prefers-color-scheme` sang cơ chế lớp `.dark`**, điều khiển bằng `next-themes` với `defaultTheme="system"` và `enableSystem`. Hành vi mặc định không đổi so với trước: vẫn bám theo cài đặt hệ điều hành, và chưa có nút cho người dùng tự chọn.
3. **Bộ biến màu cũ trong `globals.css` bị gỡ bỏ**, thay bằng bộ token của shadcn.

Component được cài từng cái theo nhu cầu từng ticket. Ticket này chỉ cài `card`.

## Các phương án đã cân nhắc

### Phương án A: Tiếp tục viết tay bằng Tailwind thuần

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp ở hôm nay, cao dần theo từng ticket tương tác |
| Chi phí vận hành | Không thêm phụ thuộc nào |
| Phù hợp lượng giao diện còn lại | Kém — ô gợi ý gõ dần và bộ chọn khoảng ngày là việc nhiều tuần |
| Khả năng tiếp cận | Rủi ro cao nhất — chuẩn ARIA combobox phải tự đọc và tự canh |
| Quyền kiểm soát mã | Tuyệt đối |

**Ưu:** không đổi gì hôm nay; không phụ thuộc mới; đúng tinh thần `CLAUDE.md` §2 và §3.
**Nhược:** chi phí dồn hết vào #11 và #12, đúng hai ticket khó nhất; khả năng tiếp cận bàn phím nhiều khả năng sai mà không ai phát hiện.

### Phương án B: Một thư viện component đóng gói (MUI, Mantine, Chakra)

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — một phụ thuộc lớn, có API riêng phải học |
| Chi phí vận hành | Trung bình — nâng cấp là thay đổi cả gói |
| Phù hợp lượng giao diện còn lại | Tốt — đủ component, đủ hành vi |
| Khả năng tiếp cận | Tốt — đã được canh sẵn |
| Quyền kiểm soát mã | Thấp — sửa hành vi phải đi qua khe cắm mà thư viện cho phép |

**Ưu:** đủ component ngay; hành vi và khả năng tiếp cận đã chín.
**Nhược:** mỗi thư viện này mang **hệ thống style riêng** — đúng cái tình huống mà ADR-0003 cảnh báo sẽ chồng lên Tailwind. Nhận nó nghĩa là phải chọn lại ADR-0003, hoặc chấp nhận hai hệ style cùng tồn tại.

### Phương án C: shadcn/ui với thư viện nền mặc định Base UI

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — mã component nằm trong repo, sửa trực tiếp |
| Chi phí vận hành | Thấp — không có gói component nào để nâng cấp |
| Phù hợp lượng giao diện còn lại | Tốt — có đủ `select`, `popover`, `calendar`, `command`, `chart` |
| Khả năng tiếp cận | Tốt — kế thừa từ thư viện nền |
| Quyền kiểm soát mã | Cao — tệp là của dự án |

**Ưu:** là đường mặc định của CLI từ 07/2026 nên được chăm sóc lâu dài; xét riêng `button`, `card`, `select`, `popover` thì nhẹ hơn Radix vì mỗi component chỉ khai `cn`.
**Nhược:** component `command` ở #12 chạy trên `cmdk`, mà `cmdk` phụ thuộc thẳng vào bốn gói `@radix-ui/react-*` **bất kể chọn thư viện nền nào**. Tới #12 repo sẽ có `@base-ui/react` nằm cạnh một nhúm gói Radix lẻ: hai thư viện nền, hai mô hình quản lý tiêu điểm, cùng phải bảo trì.

### Phương án D: shadcn/ui với thư viện nền Radix (`radix-nova`)

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — giống C |
| Chi phí vận hành | Thấp — giống C |
| Phù hợp lượng giao diện còn lại | Tốt — giống C |
| Khả năng tiếp cận | Tốt — Radix là bộ primitive lâu đời nhất trong ba lựa chọn |
| Quyền kiểm soát mã | Cao — giống C |

**Ưu:** đúng **một** thư viện nền trong repo kể cả sau khi `cmdk` vào ở #12; phần lớn ví dụ và bài viết ngoài kia giả định Radix nên các ticket giao diện sau tra cứu dễ hơn.
**Nhược:** `node_modules` nặng hơn C vì mỗi component khai gói ô `radix-ui`; Base UI mới là đường mặc định nên đường Radix có thể được chăm sóc ít dần theo thời gian.

## Phân tích đánh đổi

Đánh đổi thứ nhất nằm giữa **không thêm phụ thuộc** (A) và **chi phí dồn vào #11, #12**. Ô gợi ý gõ dần theo chuẩn ARIA combobox và bộ chọn khoảng ngày là hai thứ mà tự viết thì tốn nhiều tuần và sai lặng lẽ — người dùng bàn phím gặp lỗi mà không ai trong nhóm phát hiện. Đây không phải chỗ dự án muốn đầu tư công sức.

B giải được bài toán hành vi nhưng trả bằng đúng cái giá mà ADR-0003 đã nêu trước: một hệ thống style thứ hai chồng lên Tailwind. Điều quan trọng cần nói rõ ở đây là **shadcn không rơi vào nhóm đó**. shadcn không phải thư viện component có style riêng — nó là mã nguồn Tailwind cộng một bộ primitive không giao diện, chép thẳng vào repo. Nên nó **cộng vào** ADR-0003 chứ không chồng lên, và **ADR-0003 vẫn còn hiệu lực nguyên vẹn**: Tailwind v4 vẫn là hệ thống style duy nhất của dự án. Dòng **Cần xem lại** của ADR-0003 coi như đã được trả lời, không phải mở lại.

Đánh đổi thứ hai, giữa C và D, chỉ có một dữ kiện quyết định. Xét bốn component trước mắt thì C nhẹ hơn thật. Nhưng phép so đó dừng trước #12. Khi `command` vào, `cmdk` kéo Radix vào **trên cả hai đường**. Lúc đó lợi thế cân nặng của C biến mất, còn cái giá của nó — hai thư viện nền trong một repo — thì ở lại vĩnh viễn. D trả trước một khoản `node_modules` nặng hơn để đổi lấy một cây phụ thuộc duy nhất.

Về `CLAUDE.md` §2: nhận shadcn ở ticket này đúng là vượt phạm vi hẹp của bảng điều khiển. Nhưng phần đắt của việc nhận không phải các component mà là đợt chuyển token màu và cơ chế chế độ tối, vốn chạm vào mọi giao diện đã dựng. Hoãn lại không tiết kiệm được gì, chỉ làm đợt chuyển đổi đó đắt hơn gấp nhiều lần khi thanh bộ lọc, hai biểu đồ và sáu ô KPI đã nằm đó.

## Hệ quả

- **Dễ hơn:** #11 và #12 chỉ còn là `bunx shadcn@latest add <tên>`, không có đợt chuyển đổi nào nữa; hành vi bàn phím và khả năng tiếp cận có sẵn thay vì phải tự canh; mã component nằm trong repo nên sửa được trực tiếp khi cần, không phải chờ thư viện.
- **Khó hơn:** thêm `radix-ui`, `cn`, `class-variance-authority`, `lucide-react`, `next-themes` vào phụ thuộc chạy, cộng `shadcn` và `tw-animate-css` vào phụ thuộc phát triển — `init` đặt cả hai vào nhóm chạy, nhưng chúng chỉ được dùng lúc dựng (một cái là CLI, một cái nạp qua `@import` trong CSS) nên chuyển về đúng nhóm như `tailwindcss` sẵn có; `node_modules` nặng hơn đường Base UI; chế độ tối giờ phụ thuộc JavaScript (`next-themes` gắn lớp `.dark`) thay vì thuần CSS; các tệp trong `app/components/ui/` là mã sinh ra nhưng vẫn nằm trong tầm quét của ESLint và `tsc`.
- **Hình thức ô KPI dịch nhẹ, có chủ ý.** Bộ token và bộ đo của shadcn thay các giá trị chọn tay trước đây. Cụ thể, không chỉ màu:

  | Thuộc tính | Trước | Sau |
  | --- | --- | --- |
  | Màu chữ, chế độ sáng | `#171717` | `oklch(0.145 0 0)` |
  | Nền ô | trong suốt | `bg-card` |
  | Đường viền | `border-black/10`, nằm trong hộp | `ring-foreground/10`, vẽ ngoài hộp |
  | Bo góc | `rounded-lg`, 8px | `rounded-xl`, 14px |
  | Phần đệm | `p-5`, 20px | `--card-spacing`, 16px |
  | Thẻ gốc | `<article>` | `<div>` do `Card` dựng ra |

  Đây là cái giá phải trả để component về sau ăn cùng một bộ token và một bộ đo; ghim lại giá trị cũ thì chống lại chính hệ thống vừa nhận. Riêng thẻ gốc: `Card` không nhận cờ đổi phần tử, nên ô KPI mất vai trò `article`. Thẻ `<h2>` của nhãn thì giữ nguyên, nên cấu trúc tiêu đề dưới `<h1>` của trang không đổi.

- **Không có `app/lib/utils.ts`.** `init` sinh ra tệp một dòng `export { cn } from "cn"`, nhưng registry hiện tại cho `card`, `button`, `select`, `popover`, `calendar`, `command` và `chart` đều nhập `cn` thẳng từ gói, không qua alias — đã kiểm từng cái. Giữ lại thì đó là mã không ai dùng, trái `CLAUDE.md` §2, nên tệp bị xoá. Khoá `utils` trong `components.json` vẫn trỏ vào đường dẫn đó để nếu về sau thật sự cần thì tạo lại đúng chỗ.
- **Preset chỉ là tên bộ chủ đề, không phải cả chuỗi `style`.** CLI nhận `-b radix -p nova` để ra `style: "radix-nova"`; truyền `-p radix-nova` bị từ chối. Và CLI **không có cờ nào đặt alias**, nên các khoá alias phải sửa tay trong `components.json` ngay sau `init`, trước lệnh `add` đầu tiên.
- **Cái bẫy đang chờ #9:** component `chart` của shadcn khai `recharts@3.8.0` **kèm số phiên bản rõ ràng**. Chốt "đã cài thì thôi" của CLI chỉ bỏ qua các dòng khai tên trần, nên khi #9 chạy `add chart` thì lệnh `bun add recharts@3.8.0` sẽ chạy thẳng, **hạ cấp** bản `^3.10.1` đang có và ghi lại `bun.lock` ở gốc repo. Đã chấp nhận, nhưng người làm #9 cần biết trước để không tưởng là sự cố.
- **Cần xem lại:** Base UI là thư viện nền mặc định của shadcn từ 07/2026. Nếu đường Radix được chăm sóc ít dần — component mới ra trễ hơn, hoặc registry ngừng phát hành bản `radix-*` — thì quyết định này đáng mở lại. CLI có sẵn lệnh `shadcn migrate` cho hướng chuyển đổi đó.

## Việc cần làm

1. [x] Chạy `bunx shadcn@latest init -b radix -p nova --no-monorepo` trong `frontend/`
2. [x] Đặt các khoá alias dưới `app/` trong `components.json`; xoá `lib/utils.ts` vì registry nhập `cn` thẳng từ gói
3. [x] Xác nhận `components.json` có `style` là `radix-nova` trước khi cài component đầu tiên
4. [x] Gỡ khối `prefers-color-scheme` còn sót khỏi `app/globals.css` và định nghĩa `--font-sans`
5. [x] Thêm `next-themes` và bọc `ThemeProvider` ở layout gốc, cùng commit với việc gỡ ở trên
6. [x] Cài `card` và đổi hai ô KPI trong `dashboard.tsx` sang dùng nó
7. [x] Ghi shadcn/ui vào `frontend/README.md`
