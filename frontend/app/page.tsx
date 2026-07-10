import { ProtectedRoute } from "@/components/auth/protected-route";
import { Dashboard } from "@/components/game/dashboard";

export default function Home() {
  return (
    <ProtectedRoute>
      <Dashboard />
    </ProtectedRoute>
  );
}
