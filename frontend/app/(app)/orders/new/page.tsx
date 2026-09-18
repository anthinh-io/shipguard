import { CreateOrderForm } from "@/app/components/create-order-form";

export default function NewOrderPage() {
  return (
    // div chứ không main: SidebarInset của khung đã là thẻ <main>.
    <div className="mx-auto w-full max-w-3xl px-4 py-8">
      <CreateOrderForm />
    </div>
  );
}
