import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Verify from "./pages/Verify";
import Issuer from "./pages/Issuer";
import Console from "./pages/Console";
import { ThemeProvider } from "./components/ThemeProvider";

function App() {
  return (
    <ThemeProvider defaultTheme="system" storageKey="pramaan-theme">
      <Router>
        <div className="min-h-screen font-sans bg-background text-foreground transition-colors duration-300">
          <Routes>
            <Route path="/" element={<Navigate to="/verify" replace />} />
            <Route path="/verify" element={<Verify />} />
            <Route path="/issuer" element={<Issuer />} />
            <Route path="/console" element={<Console />} />
          </Routes>
        </div>
      </Router>
    </ThemeProvider>
  );
}

export default App;
