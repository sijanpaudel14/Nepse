import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { Sidebar } from '@/components/Sidebar';
import { Providers } from '@/components/Providers';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' });

export const metadata: Metadata = {
  title: 'NEPSE AI Trading Terminal',
  description: 'AI-Powered Swing Trading Assistant for Nepal Stock Exchange',
  icons: {
    icon: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} ${jetbrainsMono.variable} antialiased`}>
        <Providers>
          <div className="flex min-h-screen bg-background">
            {/* Sidebar Navigation */}
            <Sidebar />
            
            {/* Main Content */}
            <main className="flex-1 ml-64 p-6">
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
