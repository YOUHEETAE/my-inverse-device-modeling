import { Route, Routes, useLocation } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import HomePage from "./pages/HomePage";
import GuidePage from "./pages/GuidePage";
import CaseStudyPage from "./pages/CaseStudyPage";
import CurvesPage from "./features/curves/CurvesPage";
import FieldMapPage from "./features/fields/FieldMapPage";
import { DeviceStoreProvider } from "./features/shared/deviceStore";
import { ViewStoreProvider } from "./features/shared/viewStore";
import { PredictionCacheProvider } from "./features/shared/predictionCache";

const PAGE_META: Record<string, { title: string; breadcrumb: string[] }> = {
  "/": { title: "Home", breadcrumb: ["Inverse Device Modeling", "Home"] },
  "/guide": { title: "Guide", breadcrumb: ["Inverse Device Modeling", "Guide"] },
  "/case-study": { title: "Case Study", breadcrumb: ["Inverse Device Modeling", "Case Study"] },
  "/curves": { title: "I-V Curve Analysis", breadcrumb: ["Inverse Device Modeling", "I-V Curve"] },
  "/fields": { title: "Structure / Field Map", breadcrumb: ["Inverse Device Modeling", "Field Map"] },
};
const DEFAULT_META = { title: "Inverse Device Modeling", breadcrumb: ["Inverse Device Modeling"] };

function App() {
  const location = useLocation();
  const meta = PAGE_META[location.pathname] ?? DEFAULT_META;
  return (
    <DeviceStoreProvider>
      <ViewStoreProvider>
        <PredictionCacheProvider>
          <AppLayout title={meta.title} breadcrumb={meta.breadcrumb}>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/guide" element={<GuidePage />} />
              <Route path="/case-study" element={<CaseStudyPage />} />
              <Route path="/curves" element={<CurvesPage />} />
              <Route path="/fields" element={<FieldMapPage />} />
            </Routes>
          </AppLayout>
        </PredictionCacheProvider>
      </ViewStoreProvider>
    </DeviceStoreProvider>
  );
}

export default App;
