import { Route, Routes, useLocation } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import HomePage from "./pages/HomePage";
import CurvesPage from "./features/curves/CurvesPage";
import FieldMapPage from "./features/fields/FieldMapPage";

const PAGE_META: Record<string, { title: string; breadcrumb: string[] }> = {
  "/curves": { title: "I-V Curve Analysis", breadcrumb: ["Inverse Device Modeling", "I-V Curve"] },
  "/fields": { title: "Structure / Field Map", breadcrumb: ["Inverse Device Modeling", "Field Map"] },
};
const DEFAULT_META = { title: "Inverse Device Modeling", breadcrumb: ["Inverse Device Modeling"] };

function App() {
  const location = useLocation();
  const meta = PAGE_META[location.pathname] ?? DEFAULT_META;
  return (
    <AppLayout title={meta.title} breadcrumb={meta.breadcrumb}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/curves" element={<CurvesPage />} />
        <Route path="/fields" element={<FieldMapPage />} />
      </Routes>
    </AppLayout>
  );
}

export default App;
