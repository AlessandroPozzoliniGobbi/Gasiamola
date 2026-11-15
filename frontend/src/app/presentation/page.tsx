import type { Metadata } from "next";
import Link from "next/link";
import styles from "../../styles/presentation.module.css";

export const metadata: Metadata = {
  title: "Presentation | FIELDWISE",
  description:
    "Explore FIELDWISE through two video presentations, understand the hosted demo's limitations and find the GitHub repository for local testing.",
};

const repositoryUrl = "https://github.com/AlessandroPozzoliniGobbi/Gasiamola";

const videos = [
  {
    id: "UV4a4Smva1A",
    number: "01",
    eyebrow: "PRODUCT INTRODUCTION",
    title: "Meet FIELDWISE",
    description:
      "A short introduction to the project, the agricultural challenge and the idea behind FIELDWISE.",
  },
  {
    id: "bAd1ZywMT-Y",
    number: "02",
    eyebrow: "PLATFORM WALKTHROUGH",
    title: "See how it works",
    description:
      "A guided look at the platform's interface, analysis workflow and available features.",
  },
] as const;

export default function PresentationPage() {
  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.hero}>
          <span className={styles.eyebrow}>
            <span className={styles.dot} aria-hidden="true" />
            FIELDWISE / NASA SPACE APPS CHALLENGE 2026
          </span>
          <div className={styles.heroRow}>
            <div>
              <h1>See FIELDWISE in action.</h1>
              <p className={styles.intro}>
                Two short videos to explore our product and experience the platform
                without waiting for a full field simulation.
              </p>
            </div>
            <span className={styles.showcaseLabel}>VIDEO SHOWCASE</span>
          </div>
        </header>

        <section className={styles.videosSection} aria-labelledby="videos-heading">
          <div className={styles.sectionHead}>
            <div>
              <span className={styles.sectionNumber}>01 / WATCH</span>
              <h2 id="videos-heading">The project, in two videos.</h2>
            </div>
            <span className={styles.sectionHint}>Press play to watch directly on this page</span>
          </div>
          <div className={styles.videoGrid}>
            {videos.map((video) => (
              <article className={styles.videoCard} key={video.id}>
                <div className={styles.videoFrame}>
                  <iframe
                    title={`${video.title} — FIELDWISE video presentation`}
                    src={`https://www.youtube-nocookie.com/embed/${video.id}?rel=0`}
                    loading="lazy"
                    referrerPolicy="strict-origin-when-cross-origin"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    allowFullScreen
                  />
                </div>
                <div className={styles.videoDetails}>
                  <div className={styles.videoEyebrow}>
                    <span>{video.number}</span>
                    <span>{video.eyebrow}</span>
                  </div>
                  <h3>{video.title}</h3>
                  <p>{video.description}</p>
                  <a
                    href={`https://youtu.be/${video.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.textLink}
                  >
                    Watch on YouTube <span aria-hidden="true">↗</span>
                  </a>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className={styles.contextSection} aria-labelledby="why-heading">
          <div className={styles.contextNumber}>02 / WHY A SHOWCASE?</div>
          <div className={styles.contextBody}>
            <h2 id="why-heading">A working prototype. Not yet a frictionless online demo.</h2>
            <p>
              FIELDWISE is a functional prototype, but the public website is not yet
              optimized for fast, on-demand analyses. Preparing a new field requires
              retrieving and processing environmental data, including weather and soil
              information. On our current online hosting setup, this can take several
              minutes, and some requests may time out.
            </p>
            <p>
              That is why this page exists: the videos let you explore the project
              and its functionality immediately, even when the live demo is slow.
              The website is still available to try; just expect longer processing
              times, especially on the first analysis of a new field.
            </p>
            <div className={styles.statusRow}>
              <span className={styles.statusDot} aria-hidden="true" />
              <span>Public website: usable preview · Data-intensive operations may be slow</span>
            </div>
          </div>
        </section>

        <section className={styles.githubSection} aria-labelledby="local-heading">
          <div className={styles.githubContent}>
            <span className={styles.githubEyebrow}>03 / WANT TO TRY IT YOURSELF?</span>
            <h2 id="local-heading">Run FIELDWISE locally.</h2>
            <p>
              For a more complete hands-on experience, download or clone the project
              from GitHub and follow the repository instructions to set up the frontend
              and Python backend on your own computer. Running locally avoids some
              limitations of the public hosting environment, although the first data
              download and processing step may still take time.
            </p>
            <div className={styles.githubActions}>
              <a
                href={repositoryUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.githubButton}
              >
                Open GitHub repository <span aria-hidden="true">↗</span>
              </a>
              <Link href="/progetto" className={styles.projectLink}>
                Read the technical project <span aria-hidden="true">→</span>
              </Link>
            </div>
            <p className={styles.setupNote}>
              Local setup requires the project's dependencies and configuration.
              Follow the README before running analyses; no API keys are included
              in the public repository.
            </p>
          </div>
          <div className={styles.repoAside} aria-hidden="true">
            <div className={styles.repoWindow}>
              <div className={styles.repoDots}><i /><i /><i /></div>
              <span className={styles.repoCaption}>FIELDWISE / SOURCE CODE</span>
              <span className={styles.repoCode}>git clone</span>
              <span className={styles.repoUrl}>github.com/AlessandroPozzoliniGobbi/Gasiamola</span>
              <div className={styles.repoLine} />
              <span className={styles.repoReady}>A closer look, on your computer.</span>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
