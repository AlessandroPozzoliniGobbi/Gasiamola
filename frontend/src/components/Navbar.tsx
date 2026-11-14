import Link from "next/link";
import styles from "../styles/Navbar.module.css";
import Image from "next/image";

export default function Navbar() {
  return (
    <header className={styles.navbar}>
      <Link href="/" className={styles.brand}>
        <Image
          src="/logo/logo-icon.svg"
          alt="Logo del sito"
          width={44}
          height={44}
          priority
        />
        <span>[NOME SITO]</span>
      </Link>

      <nav className={styles.links}>
        <Link href="/">Home</Link>
        <Link href="/progetto">Progetto</Link>
        <Link href="/contatti">Contatti</Link>
        <Link href="/impostazioni" className={styles.settingsLink}>
          <span aria-hidden="true">⚙︎</span>
        </Link>
      </nav>
    </header>
  );
}
