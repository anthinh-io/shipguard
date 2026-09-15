import { OrderDetail } from "@/app/components/order-detail";

export default async function OrderDetailPage({ params }: PageProps<"/orders/[orderId]">) {
  // Next đã giải mã đoạn đường dẫn; mã đơn đi thẳng xuống, component tự mã hoá lại khi
  // gọi backend.
  const { orderId } = await params;

  return (
    // div chứ không main: SidebarInset của khung đã là thẻ <main>.
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <OrderDetail orderId={orderId} />
    </div>
  );
}
