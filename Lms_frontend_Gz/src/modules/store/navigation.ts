import type { NavItem } from "@/app/navigation";

export const storeNavigation: NavItem[] = [
  { menu: "browse_courses", label: "Browse Courses", icon: "book", to: "/browse-courses", group: "learn", hint: "Explore courses, plans and pricing" },
  { menu: "my_subscription", label: "My Subscription", icon: "award", to: "/my-subscription", group: "learn", hint: "Active plan, unlocked courses and upgrades" },
  { menu: "my_payment_requests", label: "My Payment Requests", icon: "fileText", to: "/my-payment-requests", group: "learn", hint: "Track payment requests sent to your Institution Head" },
  { menu: "payment_history", label: "Payment History", icon: "creditCard", to: "/payment-history", group: "learn", hint: "Transactions, payment status and receipts" },
  { menu: "institution_payments", label: "Student Payments", icon: "creditCard", to: "/institution-payments", group: "users", hint: "Manage student payments, requests & bulk checkout" },
];
