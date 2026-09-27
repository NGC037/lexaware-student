export const RIGHTS_DOMAINS = [
  { category: "employment", label: "Internship & Employment" },
  { category: "housing", label: "Hostel & Rental" },
  { category: "ragging", label: "Ragging" },
  { category: "cybercrime", label: "Cybercrime & Online Fraud" },
  { category: "consumer_rights", label: "Consumer Rights" },
  { category: "harassment", label: "Harassment & Safety" },
] as const;

export function categoryLabel(category: string): string {
  const domain = RIGHTS_DOMAINS.find((item) => item.category === category);
  if (domain) return domain.label;
  return category.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
