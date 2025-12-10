import type { Metadata } from "next";
import { DM_Sans, Instrument_Serif } from "next/font/google";
import "./globals.css";
import { QueryClientProviderWrapper } from "../lib/query-client-provider";
import { Toaster } from "sonner";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthProvider } from "@/contexts/auth-context";
import { UpgradeDialogProvider } from "@/contexts/upgrade-dialog-context";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  subsets: ["latin"],
  weight: "400",
});

export const metadata: Metadata = {
  title: "klipou Clip",
  description: "by klipou Clip",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${dmSans.variable} ${instrumentSerif.variable} antialiased`} suppressHydrationWarning>
        <QueryClientProviderWrapper>
          <UpgradeDialogProvider>

            <AuthProvider>
              <ThemeProvider
                attribute="class"
                defaultTheme="dark"
                enableSystem
                disableTransitionOnChange>
                {children}
              </ThemeProvider>
            </AuthProvider>
          </UpgradeDialogProvider>
          <Toaster />

        </QueryClientProviderWrapper>
      </body>
    </html >
  );
}
