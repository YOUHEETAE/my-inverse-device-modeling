import { Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import HomePage from "./pages/HomePage";
import CurvesPage from "./features/curves/CurvesPage";

function App() {
  // Only /curves is a real page so far; title/breadcrumb are hardcoded to
  // it. Once more pages exist, derive these per-route instead.
  return (
    <AppLayout title="I-V Curve Analysis" breadcrumb={["Inverse Device Modeling", "I-V Curve"]}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/curves" element={<CurvesPage />} />
      </Routes>
    </AppLayout>
  );
}

export default App;
