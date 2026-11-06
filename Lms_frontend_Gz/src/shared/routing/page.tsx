import { lazy, Suspense, type ComponentType, type ReactNode } from "react";

import { PageLoader } from "@/shared/ui";
import { isStaleBuildError, reloadForNewVersion } from "./staleBuild";

/** Wrap a lazily loaded page so a spinner shows while its code downloads. */
export function page(element: ReactNode) {
  return <Suspense fallback={<PageLoader />}>{element}</Suspense>;
}

/** Lazy-load a named export: `lazyNamed(() => import("./pages/LoginPage"), "LoginPage")`. */
export function lazyNamed<M, K extends keyof M>(loader: () => Promise<M>, name: K) {
  return lazy(() =>
    loader()
      .then((module) => ({ default: module[name] as ComponentType<Record<string, unknown>> }))
      // a tab still on the previous release asks for a file that no longer exists: load the new release instead
      .catch((error: unknown) => {
        if (isStaleBuildError(error) && reloadForNewVersion()) return new Promise<never>(() => {});
        throw error;
      }),
  ) as unknown as M[K];
}
