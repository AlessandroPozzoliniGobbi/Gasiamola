"use client";

import type { MouseEvent } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "../styles/Navbar.module.css";

const navigation = [
  { href: "/", label: "Home" },
  { href: "/progetto", label: "Project" },
  { href: "/reports", label: "Reports" },
  { href: "/contatti", label: "Team" },
];

export default function Navbar() {
  const pathname = usePathname();

  // Next/link non riporta sempre in cima se si clicca la pagina gia' aperta.
  function handleSamePageClick(event: MouseEvent<HTMLAnchorElement>, href: string) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    if (pathname === href) {
      event.preventDefault();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  function rememberSettingsOrigin() {
    try {
      sessionStorage.setItem(
        "fieldwise-settings-return-to",
        `${window.location.pathname}${window.location.search}${window.location.hash}`,
      );
    } catch {
      // La navigazione resta funzionante anche se lo storage e' disabilitato.
    }
  }

  return (
    <header className={styles.navbar}>
      <div className={styles.navbarInner}>
        <Link
          href="/"
          className={styles.brand}
          aria-label="Go to Home"
          onClick={(event) => handleSamePageClick(event, "/")}
        >
          <span className={styles.brandIcon}>
            <Image src="/logo/logo-icon.svg" alt="" width={43} height={43} priority />
          </span>
          <span className={styles.brandName}>FIELDWISE</span>
        </Link>

        <nav className={styles.navArea} aria-label="Main navigation">
          <div className={styles.links}>
            {navigation.map(({ href, label }) => {
              const active = pathname === href || ((href === "/progetto" || href === "/reports") && pathname.startsWith(`${href}/`));
              return (
                <Link
                  key={href}
                  href={href}
                  className={`${styles.navLink} ${active ? styles.active : ""}`}
                  aria-current={active ? "page" : undefined}
                  onClick={(event) => handleSamePageClick(event, href)}
                >
                  {label}
                </Link>
              );
            })}
            <span className={styles.navDivider} aria-hidden="true" />
            <Link
              href="/impostazioni"
              className={`${styles.settingsLink} ${pathname === "/impostazioni" ? styles.active : ""}`}
              aria-label="Settings"
              title="Settings"
              aria-current={pathname === "/impostazioni" ? "page" : undefined}
              onClick={(event) => {
                if (pathname === "/impostazioni") {
                  handleSamePageClick(event, "/impostazioni");
                } else {
                  rememberSettingsOrigin();
                }
              }}
            >
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M12 8.7a3.3 3.3 0 1 0 0 6.6 3.3 3.3 0 0 0 0-6.6Z" />
                <path d="M19.5 13.1v-2.2l-2-.7a6 6 0 0 0-.6-1.4l.9-1.9-1.6-1.6-1.9.9a6 6 0 0 0-1.4-.6l-.7-2h-2.2l-.7 2a6 6 0 0 0-1.4.6l-1.9-.9-1.6 1.6.9 1.9a6 6 0 0 0-.6 1.4l-2 .7v2.2l2 .7a6 6 0 0 0 .6 1.4l-.9 1.9 1.6 1.6 1.9-.9a6 6 0 0 0 1.4.6l.7 2h2.2l.7-2a6 6 0 0 0 1.4-.6l1.9.9 1.6-1.6-.9-1.9a6 6 0 0 0 .6-1.4l2-.7Z" />
              </svg>
            </Link>
          </div>
        </nav>
      </div>
    </header>
  );
}
