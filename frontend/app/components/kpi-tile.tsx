import type { ReactNode } from "react";

import { Card, CardContent } from "./ui/card";

export function KpiTile({
  testId,
  label,
  value,
  hint,
  delta,
}: {
  testId: string;
  label: string;
  value: string;
  hint?: string;
  // Mức chênh so với kỳ đối chiếu. Là ReactNode chứ không phải chuỗi vì nó gồm một mũi
  // tên và phần chữ được tô màu; value và hint đều đã là chuỗi định dạng sẵn nên không
  // có chỗ nào đặt được hai thứ đó vào.
  delta?: ReactNode;
}) {
  return (
    // Card truyền tiếp props nên data-testid xuống tới thẻ gốc; bốn bài Playwright bám
    // đúng các định danh này. Viền, nền và màu chữ phụ giờ lấy từ bộ token của shadcn
    // thay cho các giá trị chọn tay, nên chúng tự đổi theo chế độ sáng/tối.
    <Card data-testid={testId}>
      {/* Chỉ dùng CardContent: CardHeader/CardTitle dựng ra <div> và thêm một nhịp
          khoảng cách nữa, trong khi ô này chỉ cần phần đệm ngang và giữ nguyên <h2>
          để cấu trúc tiêu đề dưới <h1> của trang không mất đi. */}
      <CardContent>
        <h2 className="text-sm font-medium text-muted-foreground">{label}</h2>
        <p className="mt-2 text-4xl font-semibold tabular-nums">{value}</p>
        {delta ?? null}
        {hint ? (
          <p className="mt-2 text-sm text-muted-foreground">{hint}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
