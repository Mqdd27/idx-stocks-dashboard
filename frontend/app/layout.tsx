import type { Metadata } from "next";
import Shell from "@/components/Shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stocks IDX — Indonesia Market Dashboard",
  description: "Self-hosted Indonesian stock market dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}