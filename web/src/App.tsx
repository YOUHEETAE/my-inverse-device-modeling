import { Route, Routes, useLocation } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import HomePage from "./pages/HomePage";
import GuidePage from "./pages/GuidePage";
import CaseStudyPage from "./pages/CaseStudyPage";
import TheoryPage from "./pages/TheoryPage";
import CurvesPage from "./features/curves/CurvesPage";
import FieldMapPage from "./features/fields/FieldMapPage";
import { DeviceStoreProvider } from "./features/shared/deviceStore";
import { ViewStoreProvider } from "./features/shared/viewStore";
import { PredictionCacheProvider } from "./features/shared/predictionCache";
import { AnalysisStoreProvider } from "./features/shared/analysisStore";
import { AuthProvider } from "./features/auth/AuthProvider";

const PAGE_META: Record<string, { title: string; breadcrumb: string[] }> = {
  "/": { title: "Home", breadcrumb: ["SemiScope AI", "Home"] },
  "/guide": { title: "Guide", breadcrumb: ["SemiScope AI", "Guide"] },
  "/case-study": { title: "Case Study", breadcrumb: ["SemiScope AI", "Case Study"] },
  "/theory": { title: "Theory", breadcrumb: ["SemiScope AI", "Theory"] },
  "/curves": { title: "I-V Curve Analysis", breadcrumb: ["SemiScope AI", "I-V Curve"] },
  "/fields": { title: "Structure / Field Map", breadcrumb: ["SemiScope AI", "Field Map"] },
};
const DEFAULT_META = { title: "SemiScope AI", breadcrumb: ["SemiScope AI"] };

function App() {
  const location = useLocation();
  const meta = PAGE_META[location.pathname] ?? DEFAULT_META;
  return (
    <AuthProvider>
      <DeviceStoreProvider>
        <ViewStoreProvider>
          <PredictionCacheProvider>
            <AnalysisStoreProvider>
              <AppLayout title={meta.title} breadcrumb={meta.breadcrumb}>
                <Routes>
                  <Route path="/" element={<HomePage />} />
                  <Route path="/guide" element={<GuidePage />} />
                  <Route path="/case-study" element={<CaseStudyPage />} />
                  <Route path="/theory" element={<TheoryPage />} />
                  <Route path="/curves" element={<CurvesPage />} />
                  <Route path="/fields" element={<FieldMapPage />} />
                </Routes>
              </AppLayout>
            </AnalysisStoreProvider>
          </PredictionCacheProvider>
        </ViewStoreProvider>
      </DeviceStoreProvider>
    </AuthProvider>
  );
}

export default App;
