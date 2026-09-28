export const metadata = {
  title: "Enterprise Agent Studio — Scheduling MVP",
  description: "Local-first, governed production scheduling workspace",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif" }}>{children}</body>
    </html>
  );
}
