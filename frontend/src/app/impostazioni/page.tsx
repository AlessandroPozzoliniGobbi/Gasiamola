
"use client";

import { useRouter } from "next/navigation";

export default function Impostazioni() {
  const router = useRouter();

  return (
      <main className="project-page inner-page">
        <div className="project-page-content inner-page-content">

          <button
            type="button"
            className="project-page-back back-button"
            onClick={() => router.back()}
          >
            ← Torna indietro
          </button>

          <h1>Impostazioni</h1>

          <p>
            *Qui inseriremo le impostazioni
            dell'applicazione.*
          </p>

        </div>
      </main>
  );
}
