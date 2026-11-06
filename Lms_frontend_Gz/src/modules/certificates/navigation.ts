import type { NavItem } from "@/app/navigation";

/** CertificatesHomePage sends readers to issued certificates and template authors/reviewers to templates. */
export const certificatesNavigation: NavItem[] = [{ menu: "certificates", label: "Certificates", icon: "archive", to: "/certificates", group: "exams", hint: "Certificates for courses passed, ready to share" }];
