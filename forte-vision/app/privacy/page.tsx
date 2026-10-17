import { localizedMetadata } from "@/lib/locale-server";
import PrivacyPage from "@/components/privacy-page";

export const generateMetadata = () => localizedMetadata("Данные и cookie - Forte Vision", "Деректер және cookie - Forte Vision", "Data and cookies - Forte Vision");

export default function PrivacyNotice() {
  return <PrivacyPage />;
}
