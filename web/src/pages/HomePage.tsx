import { useEffect, useState } from "react";
import { apiClient } from "@/lib/apiClient";

export default function HomePage() {
  const [status, setStatus] = useState("checking...");

  useEffect(() => {
    apiClient
      .get<{ status: string }>("/health")
      .then((response) => setStatus(response.data.status))
      .catch(() => setStatus("unreachable"));
  }, []);

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold">Inverse Device Modeling</h1>
      <p className="mt-2 text-muted-foreground">Backend status: {status}</p>
    </div>
  );
}
