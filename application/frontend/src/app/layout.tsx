import type { Metadata } from "next";
import { Bodoni_Moda, Schibsted_Grotesk, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const display = Bodoni_Moda({
  variable: "--font-bodoni",
  subsets: ["latin"],
  style: ["normal", "italic"],
});

const body = Schibsted_Grotesk({
  variable: "--font-schibsted",
  subsets: ["latin"],
});

const mono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Policy Desk",
  description: "Ask the HR-207 leave policy and get answers that cite the section they come from.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable} h-full antialiased`}>
      <body className="h-full">{children}</body>
    </html>
  );
}
