import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api";
import { setMeta } from "../db";
import { refreshCatalogo } from "../sync";

export function Login({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const token = await login(username.trim(), password);
      await setMeta("token", token);
      await setMeta("username", username.trim());
      await refreshCatalogo();
      onLogin();
      navigate("/", { replace: true });
    } catch (err: any) {
      setError(err?.message ?? "No se pudo iniciar sesión");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login">
      <div className="logo">
        <div className="t">Verificación ISH y SDC</div>
        <div className="s">PDVSA — Inspección de campo</div>
      </div>
      <form onSubmit={submit}>
        <label className="field">
          <span>Usuario</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoCapitalize="none"
            autoCorrect="off"
            required
          />
        </label>
        <label className="field">
          <span>Contraseña</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <div className="error">{error}</div>}
        <button className="btn-primary btn-block" disabled={loading}>
          {loading ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
