import { AppShell } from "./components/layout/AppShell";
import { ReviewPage } from "./features/review/ReviewPage";

function App() {
  return (
    <AppShell>
      <ReviewPage />
    </AppShell>
  );
}

export default App;