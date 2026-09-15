import LanguageToggle from "@/app/components/language-toggle";
import { LoginForm } from "@/app/components/login-form";

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  // Đọc next ở đây rồi truyền xuống thay vì useSearchParams trong form: không phải bọc
  // Suspense. Chưa kiểm gì ở đây — form kiểm bằng safeNextPath ngay trước khi chuyển trang.
  const { next } = await searchParams;

  return (
    <main className="mx-auto w-full max-w-sm px-4 py-8">
      <div className="flex items-center justify-between gap-4">
        <span className="text-2xl font-semibold">ShipGuard</span>
        <LanguageToggle />
      </div>
      <LoginForm next={typeof next === "string" ? next : null} />
    </main>
  );
}
