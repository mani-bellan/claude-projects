import "./globals.css";

export const metadata = {
  title: "PawSpots — Pet-friendly places in India, verified",
  description:
    "Cafes, restaurants and stays across India that genuinely welcome your pet — every listing backed by dated, attributed evidence.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
