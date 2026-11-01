import "./globals.css";

export const metadata = {
  title: "WebDelta",
  description: "Track changes on web pages",
};

export default function RootLayout({ children }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}

