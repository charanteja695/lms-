import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const MediaLibraryPage = lazyNamed(() => import("./library/pages/MediaLibraryPage"), "MediaLibraryPage");

/** The video and PDF library: course authors only (the "catalog" section, then the media_library menu entry). */
export const mediaRoutes: RouteObject[] = [
  { element: <RequireSection section="catalog" />, children: [{ path: "/media-library", element: page(<MediaLibraryPage />) }] },
];
