import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Geist, Geist_Mono } from "next/font/google";
import "../styles/design-system.css";
import "../styles/global.css";
import Navbar from "../components/Navbar";
import ApplyUiPreferences from "../components/settings/ApplyUiPreferences";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FIELDWISE",
  description: "FIELDWISE - NASA Space Apps Challenge 2026",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>
        <ApplyUiPreferences />
        <Navbar />
        {children}
      </body>
    </html>
  );
}
