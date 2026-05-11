import React from "react";
import ReactDOM from "react-dom/client";

import "./styles.css";

function App() {
  return (
    <main className="app-shell">
      <section className="hero-panel">
        <p className="eyebrow">Family Cash Flow</p>
        <h1>Семейный финансовый дашборд</h1>
        <p>
          Первый frontend skeleton готов. Следующий шаг - подключить auth, импорт XLSX и
          дашборд.
        </p>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

