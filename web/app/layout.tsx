import type { Metadata } from "next";
import { Instrument_Serif } from "next/font/google";
import "./globals.css";
import { QueryClientProviderWrapper } from "../lib/query-client-provider";
import { Toaster } from "sonner";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthProvider } from "@/contexts/auth-context";
import { UpgradeDialogProvider } from "@/contexts/upgrade-dialog-context";


const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  subsets: ["latin"],
  weight: "400",
});

export const metadata: Metadata = {
  title: "klipai Clip",
  description: "by klipai Clip",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${instrumentSerif.variable} antialiased font-medium font-sans`} suppressHydrationWarning>
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
