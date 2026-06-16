import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hephaestus Studio",
  description: "Persistent local conversations for Hephaestus.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
