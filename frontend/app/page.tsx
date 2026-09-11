import Dashboard from "./components/dashboard";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8">
      <h1 className="text-2xl font-semibold">ShipGuard</h1>
      <Dashboard />
    </main>
  );
}
