import type { Metadata, Viewport } from "next";
import { Fraunces, Instrument_Sans } from "next/font/google";
import { AuthProvider } from "@/context/AuthProvider";
import { NightShell } from "@/components/NightShell";
import { TelemetryProvider } from "@/context/TelemetryProvider";
import { PwaRegister } from "@/components/PwaRegister";
import { APP_NAME } from "@/lib/config";
import "./globals.css";

// Display serif with the SOFT axis turned up: warm and rounded, like a nursery sign.
const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  axes: ["SOFT", "opsz"],
});

const instrument = Instrument_Sans({
  variable: "--font-instrument",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: APP_NAME,
  description: "A sleep-aware baby monitor",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: APP_NAME,
  },
  icons: {
    apple: "/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#0a0b15",
  viewportFit: "cover",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${fraunces.variable} ${instrument.variable} h-full`}>
      <head>
        <link rel="preload" as="script" href="/sw.js" />
      </head>
      <body className="flex min-h-full flex-col">
        <AuthProvider>
          <TelemetryProvider>
            <NightShell>{children}</NightShell>
          </TelemetryProvider>
        </AuthProvider>
        <PwaRegister />
      </body>
    </html>
  );
}
