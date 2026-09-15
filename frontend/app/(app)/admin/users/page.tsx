import { UserAdmin } from "@/app/components/user-admin";

export default function UserAdminPage() {
  return (
    // div chứ không main: SidebarInset của khung đã là thẻ <main>.
    <div className="mx-auto w-full max-w-5xl px-4 py-8">
      <UserAdmin />
    </div>
  );
}
