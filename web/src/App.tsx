import { Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import HomePage from "./pages/HomePage";
import CurvesPage from "./features/curves/CurvesPage";

function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/curves" element={<CurvesPage />} />
      </Routes>
    </AppLayout>
  );
}

export default App;
