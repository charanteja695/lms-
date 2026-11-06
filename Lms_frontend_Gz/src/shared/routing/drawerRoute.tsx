import { Suspense, type ReactNode } from "react";
import { Outlet, useNavigate } from "react-router-dom";

import { Drawer, Spinner, type DrawerSize } from "@/shared/ui";

/** A page with slide-over children: the page stays on screen (and keeps its state) while a child opens over it. */
export function WithOverlay({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <Outlet />
    </>
  );
}

function RouteDrawer({ size, children }: { size: DrawerSize; children: ReactNode }) {
  const navigate = useNavigate();
  return (
    <Drawer size={size} onClose={() => navigate("..", { relative: "path" })}>
      <div className="flex-1 px-5 py-6 sm:px-8">
        <Suspense fallback={<div className="flex justify-center py-24"><Spinner /></div>}>{children}</Suspense>
      </div>
    </Drawer>
  );
}

/** A child route shown in a slide-over above its parent page; closing goes back to the parent. Its URL still works on its own. */
export function drawerPage(element: ReactNode, size: DrawerSize = "lg") {
  return <RouteDrawer size={size}>{element}</RouteDrawer>;
}
