import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { getMeta } from "./db";
import { Login } from "./pages/Login";
import { Lista } from "./pages/Lista";
import { Formulario } from "./pages/Formulario";

export function App() {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const location = useLocation();

  useEffect(() => {
    void getMeta("token").then((t) => {
      setAuthed(!!t);
      setReady(true);
    });
  }, [location.pathname]);

  if (!ready) return null;

  return (
    <Routes>
      <Route path="/login" element={<Login onLogin={() => setAuthed(true)} />} />
      <Route path="/" element={authed ? <Lista /> : <Navigate to="/login" replace />} />
      <Route
        path="/insp/:id"
        element={authed ? <Formulario /> : <Navigate to="/login" replace />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
