/**
 * Author: Sarala Biswal
 */
import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import About from "./pages/About";
import ArchitectureView from "./pages/ArchitectureView";
import AuditTrail from "./pages/AuditTrail";
import DriftMonitor from "./pages/DriftMonitor";
import Experiments from "./pages/Experiments";
import GuardrailsView from "./pages/GuardrailsView";
import ModelRegistry from "./pages/ModelRegistry";
import PipelineRunner from "./pages/PipelineRunner";
import Settings from "./pages/Settings";

/**
 * Defines the client-side route table for the platform shell.
 */
export default function App(): JSX.Element {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<PipelineRunner />} />
        <Route path="/about" element={<About />} />
        <Route path="/architecture" element={<ArchitectureView />} />
        <Route path="/audit/:traceId" element={<AuditTrail />} />
        <Route path="/experiments" element={<Experiments />} />
        <Route path="/drift" element={<DriftMonitor />} />
        <Route path="/guardrails" element={<GuardrailsView />} />
        <Route path="/models" element={<ModelRegistry />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
