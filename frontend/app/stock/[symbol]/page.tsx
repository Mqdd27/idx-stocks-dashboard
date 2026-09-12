import { readFileSync } from "fs";
import { join } from "path";
import type { Metadata } from "next";
import StockDetailPage from "@/components/StockDetailPage";

export const dynamicParams = false;

export async function generateStaticParams() {
  const seed = JSON.parse(
    readFileSync(join(process.cwd(), "..", "collector", "seed_companies.json"), "utf8"),
  ) as Array<{ symbol: string }>;
  return seed.map((company) => ({ symbol: company.symbol }));
}

export const metadata: Metadata = { title: "Stocks IDX" };

export default async function StockPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  return <StockDetailPage symbol={symbol.toUpperCase()} />;
}