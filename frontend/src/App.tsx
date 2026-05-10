import { ResponsiveGate } from "@/components/layout/ResponsiveGate";
import { AppShell } from "@/components/layout/AppShell";

function App() {
  return (
    <ResponsiveGate>
      <AppShell />
    </ResponsiveGate>
  );
}

export default App;
