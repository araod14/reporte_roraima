import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import { registerSW } from "virtual:pwa-register";
import { App } from "./App";
import "./styles.css";
import { ThemeProvider } from "./theme";

registerSW({ immediate: true });

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider><HashRouter>
      <App />
    </HashRouter></ThemeProvider>
  </React.StrictMode>,
);
