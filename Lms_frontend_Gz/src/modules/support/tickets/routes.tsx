import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const MyTicketsPage = lazyNamed(() => import("./pages/MyTicketsPage"), "MyTicketsPage");
const MyTicketPage = lazyNamed(() => import("./pages/MyTicketPage"), "MyTicketPage");

export const myTicketRoutes: RouteObject[] = [
  { path: "/support/my-tickets", element: page(<MyTicketsPage />) },
  { path: "/support/my-tickets/:ticketId", element: page(<MyTicketPage />) },
];
