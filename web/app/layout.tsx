import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { TelemetryProvider } from "@/context/TelemetryProvider";
import { APP_NAME } from "@/lib/config";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: APP_NAME,
  description: "Sleep-aware baby monitor",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <TelemetryProvider>{children}</TelemetryProvider>
      </body>
    </html>
  );
}
