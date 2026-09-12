import Dashboard from "./components/dashboard";
import LanguageToggle from "./components/language-toggle";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8">
      {/* Nút nằm ở đây chứ không nằm trong Dashboard: Dashboard thoát sớm ở trạng thái
          đang tải và trạng thái lỗi, nên nút đặt bên trong sẽ biến mất đúng ở hai trạng
          thái mà hai bài Playwright hiện có dựng ra. */}
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">ShipGuard</h1>
        <LanguageToggle />
      </div>
      <Dashboard />
    </main>
  );
}
