"use client";

import { useRouter } from "next/navigation";

export default function Impostazioni() {
  const router = useRouter();

  function goBack() {
    // L'ultima pagina e' ricordata dalla rotellina. Un accesso diretto
    // a /impostazioni ha sempre un fallback sicuro verso la Home.
    const nextIndex = window.history.state?.idx;
    if (typeof nextIndex === "number" && nextIndex > 0) {
      router.back();
      return;
    }

    let fallback = "/";
    try {
      const saved = sessionStorage.getItem("fieldwise-settings-return-to");
      if (saved?.startsWith("/") && !saved.startsWith("//") && !saved.startsWith("/impostazioni")) {
        fallback = saved;
      }
    } catch {
      // La pagina resta navigabile senza sessionStorage.
    }
    router.push(fallback);
  }

  return (
    <main className="project-page inner-page">
      <div className="project-page-content inner-page-content">
        <button type="button" className="project-page-back back-button" onClick={goBack}>
          <span aria-hidden="true">←</span> Go back
        </button>
        <h1>Settings</h1>
        <p>Application settings will be available here.</p>
      </div>
    </main>
  );
}
