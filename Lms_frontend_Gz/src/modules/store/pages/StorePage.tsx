import { useState } from "react";

import { useGetMyCourseAccessQuery, useGetStoreOffersQuery } from "@/modules/store/api/storeApi";
import { OfferCard } from "@/modules/store/components/OfferCard";
import { PurchasesTable } from "@/modules/store/components/PurchasesTable";
import { useBuyCourse } from "@/modules/store/hooks/useBuyCourse";
import { Alert, Button, EmptyState, PageHeader, PageLoader, Tabs } from "@/shared/ui";

type Tab = "courses" | "purchases";

/** The course store for self-registered learners: buy a course, then study it in My learning. */
export function StorePage() {
  const [tab, setTab] = useState<Tab>("courses");
  const { data, isLoading, isError, refetch } = useGetStoreOffersQuery();
  const { data: access = [] } = useGetMyCourseAccessQuery();
  const { buy, busy } = useBuyCourse();
  const byCourse = new Map(access.map((a) => [a.course_id, a]));

  return (
    <>
      <PageHeader
        title="Course store"
        description="Buy a course and study it at your own pace: video and PDF lessons, a test after every topic, coding practice and a certificate when you pass."
      />
      <div className="mb-5">
        <Tabs<Tab> variant="pills" tabs={[{ value: "courses", label: "Courses" }, { value: "purchases", label: "My purchases" }]} value={tab} onChange={setTab} />
      </div>
      {tab === "purchases" ? (
        <PurchasesTable />
      ) : isLoading ? (
        <PageLoader />
      ) : isError || !data ? (
        <EmptyState icon="alert" title="Could not load the store" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
      ) : (
        <>
          {!data.payments_available && (
            <Alert tone="warning" className="mb-5" title="Payments are paused">
              Buying is not available right now. Please check back soon.
            </Alert>
          )}
          {data.offers.length === 0 ? (
            <EmptyState icon="graduation" title="No courses on sale yet" description="New courses appear here as soon as they are priced." />
          ) : (
            <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {data.offers.map((offer) => (
                <OfferCard
                  key={offer.course_id}
                  offer={offer}
                  access={byCourse.get(offer.course_id)}
                  canPay={data.payments_available && busy === null}
                  busy={busy === offer.course_id}
                  onBuy={() => void buy(offer)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
