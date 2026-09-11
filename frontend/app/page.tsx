type HealthResponse = {
  status: "ok" | "degraded";
  database: "connected" | "disconnected";
};

type BackendState =
  | { kind: "reachable"; health: HealthResponse }
  | { kind: "unreachable"; error: string };

function isHealthResponse(body: unknown): body is HealthResponse {
  return (
    typeof body === "object" &&
    body !== null &&
    ((body as HealthResponse).status === "ok" ||
      (body as HealthResponse).status === "degraded")
  );
}

async function fetchBackendHealth(backendUrl: string): Promise<BackendState> {
  try {
    const response = await fetch(`${backendUrl}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    const body: unknown = await response.json();
    if (!isHealthResponse(body)) {
      return {
        kind: "unreachable",
        error: `unexpected response (HTTP ${response.status})`,
      };
    }
    return { kind: "reachable", health: body };
  } catch (error) {
    return {
      kind: "unreachable",
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

export default async function Home() {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    throw new Error("Thiếu biến môi trường BACKEND_URL");
  }

  const state = await fetchBackendHealth(backendUrl);

  return (
    <main>
      <h1>ShipGuard</h1>
      {state.kind === "reachable" ? (
        <p data-testid="backend-status">
          Backend: {state.health.status} — Database: {state.health.database}
        </p>
      ) : (
        <p data-testid="backend-status">
          Backend: unreachable ({state.error})
        </p>
      )}
    </main>
  );
}
