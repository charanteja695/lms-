import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const TutorChatPage = lazyNamed(() => import("./pages/TutorChatPage"), "TutorChatPage");

export const chatRoutes: RouteObject[] = [
  { path: "/tutor/chat", element: page(<TutorChatPage />) },
  { path: "/tutor/chat/:conversationId", element: page(<TutorChatPage />) },
];
