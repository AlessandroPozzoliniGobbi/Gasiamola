import Image from "next/image";
import Link from "next/link";
import HomeLineArt from "../components/HomeLineArt";

export default function Home() {
  return (
    <main className="landing" id="home">
      {/* Il filo SVG continua ad attraversare tutte le sezioni della Home. */}
      <HomeLineArt />

      <section className="landing-section landing-hero" data-line-section>
        <div className="landing-scene landing-scene-hero" aria-hidden="true" />
        <div className="landing-content landing-hero-content">
          <div className="home-logo-frame">
            <Image
              src="/logo/logo-icon.svg"
              alt="Logo FIELDWISE"
              width={104}
              height={104}
              className="home-logo"
              priority
            />
          </div>
          <h1>FIELDWISE</h1>
          <p className="landing-tagline">[Catch phrase]</p>
          <div className="landing-actions">
            <Link href="/mappa" className="start-button">START</Link>
          </div>
        </div>
      </section>

      <section className="landing-section landing-step" data-line-section>
        <div className="landing-scene landing-scene-topsoil" aria-hidden="true" />
        <div className="landing-content landing-step-content">
          <span className="landing-label">01</span>
          <h2>Select Your Land</h2>
          <p className="landing-description">
            Locate your plot of land on the map and select the area you want to analyze.
            This is where it all begins: it only takes a few seconds to define your area of interest.
          </p>
        </div>
      </section>

      <section className="landing-section landing-step" data-line-section>
        <div className="landing-scene landing-scene-midsoil" aria-hidden="true" />
        <div className="landing-content landing-step-content">
          <span className="landing-label">02</span>
          <h2>Analyze with One Click</h2>
          <p className="landing-description">
            Start the analysis and let the system process the available data for your land.
            In just a few moments, you’ll receive clear and useful insights to better
            understand the area’s conditions and make more informed decisions.
          </p>
        </div>
      </section>

      <section className="landing-section landing-step" data-line-section>
        <div className="landing-scene landing-scene-deepsoil" aria-hidden="true" />
        <div className="landing-content landing-step-content">
          <span className="landing-label">03</span>
          <h2>A Project for the NASA Space Apps Challenge 2026</h2>
          <p className="landing-description">
            This project was created for the NASA Space Apps Challenge 2026, with
            the goal of tackling one of NASA’s proposed challenges through data,
            technology, and accessible tools.
            {" "}Discover the challenge we chose, the problem we aim to solve,
            and how our solution works on the Project page.
          </p>
          <Link href="/progetto" className="landing-project-link">
            Learn more <span aria-hidden="true">→</span>
          </Link>
        </div>
      </section>
    </main>
  );
}
