import { Link, Route, Routes } from "react-router-dom";

import { EmptyState } from "./components/StateViews";
import { Layout } from "./components/Layout";
import { ComparePage } from "./pages/ComparePage";
import { RunDetailPage } from "./pages/RunDetailPage";
import { RunsPage } from "./pages/RunsPage";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<RunsPage />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route
          path="*"
          element={
            <EmptyState title="Page not found.">
              <Link to="/" className="underline">Go to recorded runs</Link>
            </EmptyState>
          }
        />
      </Routes>
    </Layout>
  );
}
