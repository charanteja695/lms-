import { useState, useMemo, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import {
  useGetInstitutionCoursePricingQuery,
  useCalculateInstitutionalPurchaseMutation,
  useSubmitInstitutionRequestMutation,
} from "@/modules/billing/institutional/api/institutionalApi";
import type { PurchaseCalculation } from "@/modules/billing/institutional/types";
import { inr } from "@/modules/billing/common/format";
import { Alert, Badge, Button, Card, EmptyState, Icon, Input, PageHeader, Textarea } from "@/shared/ui";
import { useNotify } from "@/core/hooks/useNotify";

export interface InstitutionalPurchaseRequestPageProps {
  embedded?: boolean;
  onBackToRequests?: () => void;
}

export function InstitutionalPurchaseRequestPage({ embedded = false, onBackToRequests }: InstitutionalPurchaseRequestPageProps = {}) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const notify = useNotify();

  // API hooks
  const { data: pricingCourses, isLoading: isCoursesLoading } = useGetInstitutionCoursePricingQuery();
  const [calculatePurchase, { isLoading: isCalculating }] = useCalculateInstitutionalPurchaseMutation();
  const [submitRequest, { isLoading: isSubmitting }] = useSubmitInstitutionRequestMutation();

  const courses = pricingCourses ?? [];

  // Form State
  const [contactPerson, setContactPerson] = useState(user?.full_name || "");
  const [contactEmail, setContactEmail] = useState(user?.email || "");
  const [contactPhone, setContactPhone] = useState("");
  const [selectedCourseIds, setSelectedCourseIds] = useState<number[]>([]);
  const [courseSearch, setCourseSearch] = useState("");
  const [seatsRequested, setSeatsRequested] = useState<number>(100);

  // Date state: Default 6 months from next month
  const today = new Date();
  const defaultStart = new Date(today.getFullYear(), today.getMonth() + 1, 1);
  const defaultEnd = new Date(defaultStart.getFullYear(), defaultStart.getMonth() + 6, 0); // last day of 6th month

  const toYMD = (d: Date): string => d.toISOString().split("T")[0] || "";
  const [startDateStr, setStartDateStr] = useState<string>(toYMD(defaultStart));
  const [endDateStr, setEndDateStr] = useState<string>(toYMD(defaultEnd));

  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Live calculation results from backend
  const [calculation, setCalculation] = useState<PurchaseCalculation | null>(null);

  // Duration calculation in client for immediate feedback
  const durationDays = useMemo(() => {
    if (!startDateStr || !endDateStr) return 0;
    const start = new Date(startDateStr);
    const end = new Date(endDateStr);
    if (end <= start) return 0;
    const diffTime = Math.abs(end.getTime() - start.getTime());
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
  }, [startDateStr, endDateStr]);

  const durationMonths = useMemo(() => {
    return (durationDays / 30).toFixed(1);
  }, [durationDays]);

  // Toggle selection
  const toggleCourse = (courseId: number) => {
    setSelectedCourseIds((prev) =>
      prev.includes(courseId) ? prev.filter((id) => id !== courseId) : [...prev, courseId]
    );
  };

  const selectedCoursesList = useMemo(() => {
    return courses.filter((c) => selectedCourseIds.includes(Number(c.course_id)));
  }, [courses, selectedCourseIds]);

  // Recalculate whenever courses, seats, or dates change
  useEffect(() => {
    if (selectedCourseIds.length === 0 || seatsRequested <= 0 || !startDateStr || !endDateStr) {
      setCalculation(null);
      return;
    }

    const start = new Date(startDateStr);
    const end = new Date(endDateStr);
    if (end <= start) {
      setCalculation(null);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const res = await calculatePurchase({
          course_ids: selectedCourseIds,
          students: Number(seatsRequested),
          starts_at: new Date(startDateStr).toISOString(),
          ends_at: new Date(endDateStr).toISOString(),
        }).unwrap();
        setCalculation(res);
        setError(null);
      } catch (err: any) {
        // Fallback immediate client calculation if network or transient error
        setError(err?.data?.message || err?.data?.detail || null);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [selectedCourseIds, seatsRequested, startDateStr, endDateStr, calculatePurchase]);

  // Submit Handler
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (selectedCourseIds.length === 0) {
      setError("Please select at least one course from the course catalog.");
      return;
    }
    if (!seatsRequested || seatsRequested <= 0) {
      setError("Please enter a valid student capacity (number of seats).");
      return;
    }
    if (!startDateStr || !endDateStr || new Date(endDateStr) <= new Date(startDateStr)) {
      setError("Package ending date must be after starting date.");
      return;
    }
    if (!contactPerson.trim() || !contactEmail.trim() || !contactPhone.trim()) {
      setError("Please complete all contact person information fields.");
      return;
    }

    try {
      const payload = {
        contact_person: contactPerson.trim(),
        contact_email: contactEmail.trim(),
        contact_phone: contactPhone.trim(),
        requested_courses: selectedCoursesList.map((c) => ({
          course_id: Number(c.course_id),
          course_title: c.course_title,
          course_slug: c.slug,
        })),
        seats_requested: Number(seatsRequested),
        duration_days_requested: durationDays,
        starts_at: new Date(startDateStr).toISOString(),
        ends_at: new Date(endDateStr).toISOString(),
        message: message.trim() || undefined,
      };

      const result = await submitRequest(payload).unwrap();
      notify.success(
        "Quotation Request Submitted",
        `Institutional bulk purchase request #${result.public_id} submitted for Admin review.`
      );
      navigate(`/institution/course-requests/${result.public_id}`);
    } catch (err: any) {
      setError(err?.data?.detail || err?.data?.message || "Failed to submit request. Please review the errors.");
    }
  };

  const filteredCourses = useMemo(() => {
    if (!courseSearch.trim()) return courses;
    const q = courseSearch.toLowerCase();
    return courses.filter(
      (c) =>
        c.course_title.toLowerCase().includes(q) ||
        String(c.course_id).includes(q) ||
        (c.category && c.category.toLowerCase().includes(q))
    );
  }, [courses, courseSearch]);

  return (
    <div className="mx-auto max-w-6xl py-2 space-y-6">
      {!embedded ? (
        <PageHeader
          title="Institutional Bulk Course Purchase & Pricing Calculator"
          description="Select multiple courses, specify your student capacity, choose package start and end dates, and get an immediate authoritative quotation breakdown."
          backTo="/institution/purchases"
          backLabel="Back to Institutional Purchases"
        />
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-4 rounded-2xl border border-slate-200/80 shadow-sm">
          <div>
            <h3 className="text-sm font-bold text-navy-950">Dynamic Institutional Bulk Course Calculator</h3>
            <p className="text-xs text-slate-500">
              Select multiple courses, specify student count and date ranges to calculate custom institutional pricing.
            </p>
          </div>
          {onBackToRequests && (
            <Button variant="secondary" size="sm" onClick={onBackToRequests}>
              <Icon name="arrowLeft" size={14} /> Back to Requests
            </Button>
          )}
        </div>
      )}

      {error && (
        <Alert tone="error" title="Validation / Pricing Error">
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Step 1: Select Courses */}
        <Card
          title="Step 1 – Select Courses"
          description="Search and choose one or more courses to license for your institution's students."
        >
          <div className="space-y-4">
            <div className="relative">
              <Input
                type="text"
                placeholder="Search courses by title or subject..."
                value={courseSearch}
                onChange={(e) => setCourseSearch(e.target.value)}
                className="pl-9"
              />
              <div className="absolute left-3 top-3 text-slate-400">
                <Icon name="search" size={16} />
              </div>
            </div>

            {isCoursesLoading ? (
              <p className="text-xs text-slate-400 py-4">Loading course catalog & institutional pricing...</p>
            ) : filteredCourses.length === 0 ? (
              <EmptyState
                icon="book"
                title="No Courses Found"
                description="No courses match your search criteria."
              />
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 max-h-72 overflow-y-auto pr-1 border border-slate-100 rounded-xl p-2 bg-slate-50/50">
                {filteredCourses.map((course) => {
                  const cid = Number(course.course_id);
                  const isSelected = selectedCourseIds.includes(cid);

                  let rateStr = "";
                  if (course.pricing_method === "fixed") {
                    rateStr = `${inr(course.fixed_price_paise)} / student`;
                  } else if (course.pricing_method === "monthly") {
                    rateStr = `${inr(course.monthly_price_paise)} / mo`;
                  } else if (course.pricing_method === "hourly") {
                    rateStr = `${inr(course.hourly_price_paise)} / hr (${course.billable_hours || 40}h)`;
                  }

                  return (
                    <div
                      key={cid}
                      onClick={() => toggleCourse(cid)}
                      className={`flex flex-col justify-between p-3 rounded-xl border cursor-pointer transition select-none ${
                        isSelected
                          ? "border-blue-600 bg-blue-50/80 shadow-sm ring-1 ring-blue-500/20"
                          : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-xs"
                      }`}
                    >
                      <div className="flex items-start gap-2.5">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {}}
                          className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="font-bold text-slate-900 text-xs truncate" title={course.course_title}>
                            {course.course_title}
                          </p>
                          <p className="text-[11px] text-slate-500">{course.category || "Technology"}</p>
                        </div>
                      </div>

                      <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
                        <span className="font-semibold text-blue-900">{rateStr}</span>
                        <Badge
                          tone={
                            course.pricing_method === "fixed"
                              ? "blue"
                              : course.pricing_method === "monthly"
                              ? "purple"
                              : "amber"
                          }
                        >
                          {(course.pricing_method || "fixed").toUpperCase()}
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {selectedCourseIds.length > 0 && (
              <div className="flex items-center justify-between p-3 bg-blue-50/70 border border-blue-200 rounded-xl text-xs text-blue-900">
                <span className="font-medium">
                  Selected <span className="font-bold">{selectedCourseIds.length} course{selectedCourseIds.length > 1 ? "s" : ""}</span>:{" "}
                  {selectedCoursesList.map((c) => c.course_title).join(", ")}
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedCourseIds([])}
                  className="font-bold text-blue-600 hover:underline"
                >
                  Clear All
                </button>
              </div>
            )}
          </div>
        </Card>

        {/* Step 2 & 3: Student Capacity & Package Duration */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card
            title="Step 2 – Student Capacity (Seats)"
            description="Enter the total number of students who will receive access."
          >
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Number of Students <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <Input
                    type="number"
                    min={1}
                    max={50000}
                    value={seatsRequested}
                    onChange={(e) => setSeatsRequested(Math.max(1, Number(e.target.value)))}
                    required
                    className="font-bold text-slate-900 text-sm"
                  />
                  <span className="absolute right-3 top-2.5 text-xs text-slate-400 font-medium">seats</span>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">
                  Tiered volume discounts will be applied automatically based on total seats.
                </p>
              </div>

              <div className="flex flex-wrap gap-2 pt-1">
                <span className="text-[11px] text-slate-400 self-center">Quick presets:</span>
                {[50, 100, 200, 500, 1000].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSeatsRequested(s)}
                    className={`text-xs px-2.5 py-1 rounded-md border font-medium ${
                      seatsRequested === s
                        ? "bg-blue-600 text-white border-blue-600 shadow-xs"
                        : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                    }`}
                  >
                    {s} Seats
                  </button>
                ))}
              </div>
            </div>
          </Card>

          <Card
            title="Step 3 – Package Duration"
            description="Select package starting date and ending date."
          >
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Starting Date <span className="text-red-500">*</span>
                  </label>
                  <Input
                    type="date"
                    value={startDateStr}
                    onChange={(e) => setStartDateStr(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Ending Date <span className="text-red-500">*</span>
                  </label>
                  <Input
                    type="date"
                    value={endDateStr}
                    onChange={(e) => setEndDateStr(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between text-xs text-slate-700">
                <span>Calculated Duration:</span>
                <span className="font-bold text-slate-900">
                  {durationDays} Calendar Days ({durationMonths} Months)
                </span>
              </div>

              <div className="flex flex-wrap gap-2">
                <span className="text-[11px] text-slate-400 self-center">Presets from start:</span>
                {[
                  { label: "3 Months", months: 3 },
                  { label: "6 Months", months: 6 },
                  { label: "1 Year", months: 12 },
                ].map((p) => (
                  <button
                    key={p.label}
                    type="button"
                    onClick={() => {
                      const s = new Date(startDateStr || new Date());
                      const e = new Date(s.getFullYear(), s.getMonth() + p.months, s.getDate() - 1);
                      setEndDateStr(toYMD(e));
                    }}
                    className="text-xs px-2.5 py-1 bg-white border border-slate-200 rounded-md text-slate-700 hover:bg-slate-50 font-medium"
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          </Card>
        </div>

        {/* Step 4: Automatic Course-Wise Pricing Breakdown Table */}
        {selectedCourseIds.length > 0 && calculation && (
          <Card
            title="Step 4 – Automatic Course-Wise Pricing Breakdown"
            description="Real-time authoritative cost breakdown calculated by the backend pricing engine."
          >
            <div className="overflow-x-auto border border-slate-200 rounded-xl overflow-hidden">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50 uppercase text-[11px] text-slate-500 font-semibold border-b">
                  <tr>
                    <th className="px-4 py-3">Course</th>
                    <th className="px-4 py-3">Pricing Method</th>
                    <th className="px-4 py-3">Rate</th>
                    <th className="px-4 py-3">Students</th>
                    <th className="px-4 py-3">Duration / Units</th>
                    <th className="px-4 py-3 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {calculation.course_breakdown.map((row) => (
                    <tr key={row.course_id} className="hover:bg-slate-50/60">
                      <td className="px-4 py-3 font-bold text-slate-900">{row.course_title}</td>
                      <td className="px-4 py-3">
                        <Badge tone="blue">{row.pricing_method.toUpperCase()}</Badge>
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-700">{row.rate_label}</td>
                      <td className="px-4 py-3 font-semibold text-slate-900">{row.students} seats</td>
                      <td className="px-4 py-3 text-slate-600">{row.duration_label}</td>
                      <td className="px-4 py-3 text-right font-bold text-slate-900">
                        {inr(row.subtotal_paise)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* Step 5: Live Price Summary & Checkout Review */}
        {calculation && (
          <div className="bg-gradient-to-br from-blue-900 via-slate-900 to-indigo-950 text-white rounded-2xl p-6 shadow-xl space-y-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-white/10 gap-2">
              <div>
                <span className="text-[11px] font-bold tracking-widest text-blue-300 uppercase">
                  Institutional Bulk Purchase Summary
                </span>
                <h3 className="text-xl font-bold text-white mt-0.5">
                  {user?.institution?.name || "Institution Purchase Quotation"}
                </h3>
              </div>
              <div className="text-right">
                <span className="text-xs text-blue-200">
                  {calculation.total_students} Seats · {calculation.course_breakdown.length} Courses · {calculation.total_duration_days} Days
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2 text-xs text-blue-100">
                <p>
                  <span className="text-blue-300">Package Dates:</span>{" "}
                  {new Date(calculation.starts_at).toLocaleDateString()} to{" "}
                  {new Date(calculation.ends_at).toLocaleDateString()} ({calculation.total_duration_days} Days)
                </p>
                <p>
                  <span className="text-blue-300">Courses Included:</span>{" "}
                  {calculation.course_breakdown.map((c) => c.course_title).join(", ")}
                </p>
                <p className="text-[11px] text-blue-200/80 pt-2">
                  * All prices are authoritatively verified by the backend. Upon submission, an official quotation is registered for Admin approval.
                </p>
              </div>

              {/* Price Calculation Box */}
              <div className="bg-white/10 rounded-xl p-4 border border-white/15 space-y-2.5 text-xs">
                <div className="flex justify-between text-blue-100">
                  <span>Course Subtotal:</span>
                  <span className="font-semibold text-white">{inr(calculation.subtotal_paise)}</span>
                </div>

                <div className="flex justify-between text-emerald-300 font-medium">
                  <span>Bulk Volume Discount ({calculation.bulk_discount_percent}%):</span>
                  <span>- {inr(calculation.bulk_discount_paise)}</span>
                </div>
                {calculation.bulk_discount_note && (
                  <p className="text-[10px] text-emerald-200 text-right">{calculation.bulk_discount_note}</p>
                )}

                <div className="flex justify-between text-blue-100 pt-1 border-t border-white/10">
                  <span>Taxable Amount:</span>
                  <span className="font-semibold text-white">{inr(calculation.taxable_paise)}</span>
                </div>

                <div className="flex justify-between text-blue-100">
                  <span>GST ({calculation.gst_percent}%):</span>
                  <span className="font-semibold text-white">{inr(calculation.gst_paise)}</span>
                </div>

                <div className="flex justify-between text-base font-bold text-white pt-2 border-t border-white/20">
                  <span>Grand Total (Payable):</span>
                  <span className="text-emerald-400 text-xl">{inr(calculation.grand_total_paise)}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Contact Information & Submit */}
        <Card title="Contact Person & Notes for Quotation">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Contact Person Name <span className="text-red-500">*</span>
              </label>
              <Input
                value={contactPerson}
                onChange={(e) => setContactPerson(e.target.value)}
                placeholder="e.g. Dr. Rajesh Sharma"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Official Email <span className="text-red-500">*</span>
              </label>
              <Input
                type="email"
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
                placeholder="e.g. principal@college.edu"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Official Phone <span className="text-red-500">*</span>
              </label>
              <Input
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                placeholder="e.g. +91 9876543210"
                required
              />
            </div>
          </div>

          <div className="mt-4">
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Additional Requirements or Notes (Optional)
            </label>
            <Textarea
              rows={2}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="e.g. Requesting formal quotation for Board of Trustees approval."
            />
          </div>
        </Card>

        {/* Submit Actions */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={() => navigate("/institution/purchases")}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={isSubmitting || isCalculating}
            disabled={selectedCourseIds.length === 0 || !calculation}
          >
            <Icon name="check" size={16} />
            Submit Purchase Request & Receive Quotation
          </Button>
        </div>
      </form>
    </div>
  );
}

export default InstitutionalPurchaseRequestPage;
