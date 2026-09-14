import { OrderList } from "@/app/components/order-list";
import { parseOrderListParams } from "@/app/lib/order-list-params";

export default async function OrdersPage({ searchParams }: PageProps<"/orders">) {
  // Đọc tham số ở đây rồi truyền xuống thay vì useSearchParams trong component: không phải
  // bọc Suspense. router.push/replace ở phía client dựng lại trang này với tham số mới.
  const params = parseOrderListParams(await searchParams);

  return (
    // div chứ không main: SidebarInset của khung đã là thẻ <main>.
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <OrderList params={params} />
    </div>
  );
}
