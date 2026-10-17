import { localizedMetadata } from "@/lib/locale-server";
import NotFoundScreen from "@/components/not-found-screen";

export const generateMetadata = () => localizedMetadata("Страница не найдена - Forte Vision", "Бет табылмады - Forte Vision", "Page not found - Forte Vision", { robots: { index: false, follow: true } });

export default function NotFound() {
  return <NotFoundScreen />;
}
