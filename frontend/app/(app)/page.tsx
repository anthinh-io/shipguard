import Dashboard from "@/app/components/dashboard";

export default function Home() {
  return (
    // div chứ không main: SidebarInset của khung đã là thẻ <main>.
    <div className="mx-auto w-full max-w-5xl px-4 py-8">
      <Dashboard />
    </div>
  );
}
