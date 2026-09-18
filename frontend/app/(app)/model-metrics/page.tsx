import { ModelMetrics } from "@/app/components/model-metrics";

export default function ModelMetricsPage() {
  // div chứ không main: SidebarInset của khung đã là thẻ <main>.
  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8">
      <ModelMetrics />
    </div>
  );
}
