import Dashboard from "@/app/components/dashboard";
import { parseDashboardFilters } from "@/app/lib/dashboard-filters";

export default async function Home({ searchParams }: PageProps<"/">) {
  // Cùng khuôn với orders/page.tsx: đọc tham số ở đây rồi truyền xuống thay vì
  // useSearchParams trong component. router.push ở phía client dựng lại trang này với bộ
  // lọc mới, và bấm Back cũng vậy.
  const filters = parseDashboardFilters(await searchParams);

  return (
    // div chứ không main: SidebarInset của khung đã là thẻ <main>.
    <div className="mx-auto w-full max-w-5xl px-4 py-8">
      <Dashboard filters={filters} />
    </div>
  );
}
