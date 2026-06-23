import type { Metadata } from "next";

import "@fontsource/azeret-mono/400.css";
import "@fontsource/azeret-mono/700.css";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/700.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Foundry — LLMOps Workbench",
  description: "LangChain RAG, TAG, CAG 파이프라인을 구성하고 검증하는 로컬 워크벤치",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
