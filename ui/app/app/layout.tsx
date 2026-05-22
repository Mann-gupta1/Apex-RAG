import "./globals.css";
import type { Metadata } from "next";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

export const metadata: Metadata = {
  title: "Apex RAG — Control Plane",
  description: "Multi-Modal Enterprise Search",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <div className="grid grid-cols-[240px_1fr] min-h-screen">
          <Sidebar />
          <div className="flex flex-col min-w-0">
            <Header />
            <main className="flex-1 p-6 overflow-x-hidden">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
