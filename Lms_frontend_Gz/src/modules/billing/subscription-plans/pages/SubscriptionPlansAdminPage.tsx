import { useEffect, useState } from "react";

import { useAppDispatch } from "@/app/hooks";
import { toApiError } from "@/core/lib/apiError";
import { cn } from "@/core/lib/cn";
import { toastAdded } from "@/core/toast/toastSlice";
import { BillingTabs } from "@/modules/billing/common/components/BillingTabs";
import { toPaise } from "@/modules/billing/common/format";
import {
  type PaymentSettingsInput,
  type PlanUpsertInput,
  useAdminCreateSubscriptionPlanMutation,
  useAdminDeleteSubscriptionPlanMutation,
  useAdminGetPaymentSettingsQuery,
  useAdminListSubscriptionPlansQuery,
  useAdminUpdatePaymentSettingsMutation,
  useAdminUpdateSubscriptionPlanMutation,
} from "@/modules/billing/subscription-plans/api/studentPlansAdminApi";
import { PlanTierCard } from "@/modules/store/components/PlanTierCard";
import type { CertificateLevel, SubscriptionPlan } from "@/modules/store/studentTypes";
import {
  Button,
  Card,
  Checkbox,
  ConfirmDialog,
  Field,
  Icon,
  Input,
  Modal,
  PageHeader,
  Select,
  Spinner,
  Textarea,
} from "@/shared/ui";

interface PlanFormState {
  code: string;
  name: string;
  description: string;
  priceRupees: string;
  minPriceRupees: string;
  maxPriceRupees: string;
  durationDays: string;
  billingLabel: string;
  unlimitedCourses: boolean;
  maxCourses: string;
  featuresText: string;
  chapterTests: boolean;
  moduleTests: boolean;
  finalExam: boolean;
  proctoring: boolean;
  certificateLevel: CertificateLevel;
  supportTier: string;
  isActive: boolean;
  isRecommended: boolean;
  tierRank: string;
}

function emptyForm(): PlanFormState {
  return {
    code: "",
    name: "",
    description: "",
    priceRupees: "999",
    minPriceRupees: "499",
    maxPriceRupees: "4999",
    durationDays: "30",
    billingLabel: "month",
    unlimitedCourses: false,
    maxCourses: "10",
    featuresText: "Access to 10 courses\nChapter & Module Tests\nPremium Certificate\nPriority Support",
    chapterTests: true,
    moduleTests: true,
    finalExam: false,
    proctoring: false,
    certificateLevel: "premium",
    supportTier: "Priority Support",
    isActive: true,
    isRecommended: false,
    tierRank: "2",
  };
}

function formFromPlan(p: SubscriptionPlan): PlanFormState {
  return {
    code: p.code,
    name: p.name,
    description: p.description,
    priceRupees: String(Math.round(p.price_paise / 100)),
    minPriceRupees: p.min_price_paise != null ? String(Math.round(p.min_price_paise / 100)) : "",
    maxPriceRupees: p.max_price_paise != null ? String(Math.round(p.max_price_paise / 100)) : "",
    durationDays: String(p.billing_duration_days),
    billingLabel: p.billing_label,
    unlimitedCourses: p.max_courses == null,
    maxCourses: p.max_courses != null ? String(p.max_courses) : "",
    featuresText: (p.features || []).join("\n"),
    chapterTests: Boolean(p.assessment_access?.chapter_tests),
    moduleTests: Boolean(p.assessment_access?.module_tests),
    finalExam: Boolean(p.assessment_access?.final_exam),
    proctoring: Boolean(p.assessment_access?.proctoring),
    certificateLevel: p.certificate_level,
    supportTier: p.support_tier,
    isActive: p.is_active,
    isRecommended: p.is_recommended,
    tierRank: String(p.tier_rank),
  };
}

const METHOD_LABELS: Array<{ key: string; label: string }> = [
  { key: "razorpay", label: "Razorpay" },
  { key: "stripe", label: "Stripe" },
  { key: "upi", label: "UPI" },
  { key: "cards", label: "Cards" },
  { key: "netbanking", label: "Net Banking" },
  { key: "wallet", label: "Wallet" },
];

const UPGRADE_MODE_OPTIONS = [
  { value: "price_difference", label: "Price Difference" },
  { value: "full_price", label: "Full Plan Price" },
];

const CERT_LEVEL_OPTIONS = [
  { value: "none", label: "None" },
  { value: "basic", label: "Basic" },
  { value: "premium", label: "Premium" },
  { value: "pro", label: "Pro" },
];

export function SubscriptionPlansAdminPage() {
  const dispatch = useAppDispatch();
  const { data: plans = [], isLoading: loadingPlans } = useAdminListSubscriptionPlansQuery();
  const { data: settings, isLoading: loadingSettings } = useAdminGetPaymentSettingsQuery();

  const [createPlan, { isLoading: creating }] = useAdminCreateSubscriptionPlanMutation();
  const [updatePlan, { isLoading: updating }] = useAdminUpdateSubscriptionPlanMutation();
  const [deletePlan, { isLoading: deleting }] = useAdminDeleteSubscriptionPlanMutation();
  const [saveSettings, { isLoading: savingSettings }] = useAdminUpdatePaymentSettingsMutation();

  const [editingPlan, setEditingPlan] = useState<SubscriptionPlan | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<PlanFormState>(emptyForm);
  const [deletingTarget, setDeletingTarget] = useState<SubscriptionPlan | null>(null);

  const [settingsForm, setSettingsForm] = useState<PaymentSettingsInput>({
    payments_enabled: true,
    min_amount_paise: 49900,
    max_amount_paise: 499900,
    accepted_methods: { razorpay: true, stripe: false, upi: true, cards: true, netbanking: true, wallet: true },
    tax_rate_percent: 0,
    upgrade_pricing_mode: "price_difference",
    upi_vpa: "examlms@icici",
    upi_merchant_name: "ExamLMS",
  });
  const [minRupees, setMinRupees] = useState("499");
  const [maxRupees, setMaxRupees] = useState("4999");

  useEffect(() => {
    if (!settings) return;
    setSettingsForm({
      payments_enabled: settings.payments_enabled,
      min_amount_paise: settings.min_amount_paise,
      max_amount_paise: settings.max_amount_paise,
      accepted_methods: { ...settings.accepted_methods },
      tax_rate_percent: settings.tax_rate_percent,
      upgrade_pricing_mode: settings.upgrade_pricing_mode,
      upi_vpa: settings.upi_vpa,
      upi_merchant_name: settings.upi_merchant_name,
    });
    setMinRupees(String(Math.round(settings.min_amount_paise / 100)));
    setMaxRupees(String(Math.round(settings.max_amount_paise / 100)));
  }, [settings]);

  const openCreate = () => {
    setEditingPlan(null);
    setForm(emptyForm());
    setModalOpen(true);
  };

  const openEdit = (plan: SubscriptionPlan) => {
    setEditingPlan(plan);
    setForm(formFromPlan(plan));
    setModalOpen(true);
  };

  const handleSavePlan = async () => {
    const features = form.featuresText
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

    const payload: PlanUpsertInput = {
      code: form.code.trim().toLowerCase(),
      name: form.name.trim(),
      description: form.description.trim(),
      price_paise: toPaise(form.priceRupees || "0"),
      min_price_paise: form.minPriceRupees ? toPaise(form.minPriceRupees) : null,
      max_price_paise: form.maxPriceRupees ? toPaise(form.maxPriceRupees) : null,
      billing_duration_days: Math.max(1, Number(form.durationDays) || 30),
      billing_label: form.billingLabel.trim() || "month",
      max_courses: form.unlimitedCourses ? null : Math.max(1, Number(form.maxCourses) || 1),
      clear_max_courses: form.unlimitedCourses,
      features,
      course_access_rules: { all_approved_courses: true, course_ids: [] },
      assessment_access: {
        chapter_tests: form.chapterTests,
        module_tests: form.moduleTests,
        final_exam: form.finalExam,
        proctoring: form.proctoring,
      },
      certificate_level: form.certificateLevel,
      support_tier: form.supportTier.trim() || "Email Support",
      is_active: form.isActive,
      is_recommended: form.isRecommended,
      display_order: Math.max(0, Number(form.tierRank) || 1),
      tier_rank: Math.max(1, Number(form.tierRank) || 1),
    };

    try {
      if (editingPlan) {
        await updatePlan({ planId: editingPlan.plan_id, ...payload }).unwrap();
        dispatch(toastAdded({ tone: "success", title: "Plan updated", description: `${payload.name} saved.` }));
      } else {
        await createPlan(payload).unwrap();
        dispatch(toastAdded({ tone: "success", title: "Plan created", description: `${payload.name} added.` }));
      }
      setModalOpen(false);
    } catch (err) {
      dispatch(toastAdded({ tone: "error", title: "Could not save plan", description: toApiError(err).message }));
    }
  };

  const handleConfirmDelete = async () => {
    if (!deletingTarget) return;
    try {
      await deletePlan(deletingTarget.plan_id).unwrap();
      dispatch(toastAdded({ tone: "success", title: "Plan removed", description: `${deletingTarget.name} deleted or archived.` }));
      setDeletingTarget(null);
    } catch (err) {
      dispatch(toastAdded({ tone: "error", title: "Delete failed", description: toApiError(err).message }));
    }
  };

  const handleSaveSettings = async () => {
    try {
      await saveSettings({
        ...settingsForm,
        min_amount_paise: toPaise(minRupees || "0"),
        max_amount_paise: toPaise(maxRupees || "0"),
      }).unwrap();
      dispatch(toastAdded({ tone: "success", title: "Payment settings saved" }));
    } catch (err) {
      dispatch(toastAdded({ tone: "error", title: "Could not update payment settings", description: toApiError(err).message }));
    }
  };

  return (
    <>
      <PageHeader
        title="Subscription Plans & Payment Settings"
        description="Configure Base, Silver, Gold, and custom student plans along with global gateway settings."
      />
      <BillingTabs />

      {loadingPlans || loadingSettings ? (
        <div className="flex min-h-[260px] items-center justify-center">
          <Spinner />
        </div>
      ) : (
        <div className="grid gap-6 xl:grid-cols-12">
          <Card className="xl:col-span-8" bodyClassName="p-6">
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-navy-950">Subscription Plans</h2>
                <p className="text-xs text-slate-500">Create and manage course subscription plans</p>
              </div>
              <Button variant="primary" onClick={openCreate}>
                <Icon name="plus" size={16} />
                Add Plan
              </Button>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {plans.map((plan) => (
                <PlanTierCard
                  key={plan.plan_id}
                  plan={plan}
                  footerActions={
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="secondary" className="flex-1" onClick={() => openEdit(plan)}>
                        <Icon name="edit" size={14} />
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-red-600 hover:bg-red-50 hover:text-red-700"
                        onClick={() => setDeletingTarget(plan)}
                        aria-label={`Delete ${plan.name}`}
                      >
                        <Icon name="trash" size={15} />
                      </Button>
                    </div>
                  }
                />
              ))}
            </div>
          </Card>

          <Card className="xl:col-span-4" bodyClassName="space-y-5 p-6">
            <div>
              <h2 className="text-lg font-bold text-navy-950">Payment Settings</h2>
              <p className="text-xs text-slate-500">Configure pricing and payment options</p>
            </div>

            <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/70 p-3.5">
              <div>
                <div className="text-sm font-semibold text-navy-950">Enable Course Payments</div>
                <div className="text-xs text-slate-500">Allow students to purchase courses and subscriptions</div>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={settingsForm.payments_enabled}
                onClick={() => setSettingsForm((s) => ({ ...s, payments_enabled: !s.payments_enabled }))}
                className={cn(
                  "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
                  settingsForm.payments_enabled ? "bg-brand-600" : "bg-slate-300",
                )}
              >
                <span
                  className={cn(
                    "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition",
                    settingsForm.payments_enabled ? "translate-x-5" : "translate-x-0",
                  )}
                />
              </button>
            </div>

            <div>
              <div className="text-sm font-semibold text-navy-950">Payment Range (₹)</div>
              <div className="text-xs text-slate-500">Set minimum and maximum course plan price</div>
              <div className="mt-2.5 flex items-center gap-2">
                <div className="relative flex-1">
                  <span className="pointer-events-none absolute left-3 top-2.5 text-xs font-semibold text-slate-400">₹</span>
                  <Input
                    type="number"
                    min={0}
                    className="pl-7"
                    value={minRupees}
                    onChange={(e) => setMinRupees(e.target.value)}
                  />
                </div>
                <span className="text-slate-400">—</span>
                <div className="relative flex-1">
                  <span className="pointer-events-none absolute left-3 top-2.5 text-xs font-semibold text-slate-400">₹</span>
                  <Input
                    type="number"
                    min={0}
                    className="pl-7"
                    value={maxRupees}
                    onChange={(e) => setMaxRupees(e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div>
              <div className="text-sm font-semibold text-navy-950">Accepted Payment Methods</div>
              <div className="text-xs text-slate-500">Choose payment gateways shown at checkout</div>
              <div className="mt-2.5 grid grid-cols-2 gap-2.5">
                {METHOD_LABELS.map((m) => (
                  <Checkbox
                    key={m.key}
                    label={m.label}
                    checked={Boolean(settingsForm.accepted_methods[m.key])}
                    onChange={(e) =>
                      setSettingsForm((s) => ({
                        ...s,
                        accepted_methods: { ...s.accepted_methods, [m.key]: e.target.checked },
                      }))
                    }
                  />
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Tax / GST (%)">
                {(props) => (
                  <Input
                    {...props}
                    type="number"
                    min={0}
                    max={28}
                    value={settingsForm.tax_rate_percent}
                    onChange={(e) => setSettingsForm((s) => ({ ...s, tax_rate_percent: Number(e.target.value) || 0 }))}
                  />
                )}
              </Field>
              <Field label="Upgrade Mode">
                {(props) => (
                  <Select
                    {...props}
                    options={UPGRADE_MODE_OPTIONS}
                    value={settingsForm.upgrade_pricing_mode}
                    onChange={(e) =>
                      setSettingsForm((s) => ({
                        ...s,
                        upgrade_pricing_mode: e.target.value as "price_difference" | "full_price",
                      }))
                    }
                  />
                )}
              </Field>
            </div>

            <Field label="Merchant UPI VPA">
              {(props) => (
                <Input
                  {...props}
                  value={settingsForm.upi_vpa}
                  onChange={(e) => setSettingsForm((s) => ({ ...s, upi_vpa: e.target.value }))}
                />
              )}
            </Field>

            <Button className="w-full" variant="primary" loading={savingSettings} onClick={handleSaveSettings}>
              <Icon name="save" size={16} />
              Save Settings
            </Button>
          </Card>
        </div>
      )}

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        size="lg"
        title={editingPlan ? `Edit ${editingPlan.name}` : "Add Subscription Plan"}
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" loading={creating || updating} onClick={handleSavePlan}>
              {editingPlan ? "Save Changes" : "Create Plan"}
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Plan Code (unique slug)">
            {(props) => (
              <Input
                {...props}
                value={form.code}
                disabled={Boolean(editingPlan)}
                placeholder="e.g. platinum"
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
              />
            )}
          </Field>
          <Field label="Plan Name">
            {(props) => (
              <Input
                {...props}
                value={form.name}
                placeholder="e.g. Silver Plan"
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            )}
          </Field>
          <Field label="Price (₹)">
            {(props) => (
              <Input
                {...props}
                type="number"
                min={0}
                value={form.priceRupees}
                onChange={(e) => setForm((f) => ({ ...f, priceRupees: e.target.value }))}
              />
            )}
          </Field>
          <Field label="Duration (Days) & Label">
            {(props) => (
              <div className="flex gap-2">
                <Input
                  {...props}
                  type="number"
                  min={1}
                  value={form.durationDays}
                  onChange={(e) => setForm((f) => ({ ...f, durationDays: e.target.value }))}
                />
                <Input
                  value={form.billingLabel}
                  placeholder="month"
                  onChange={(e) => setForm((f) => ({ ...f, billingLabel: e.target.value }))}
                />
              </div>
            )}
          </Field>

          <Field label="Max Courses Allowed">
            {(props) => (
              <div className="space-y-2">
                <Checkbox
                  label="Unlimited courses"
                  checked={form.unlimitedCourses}
                  onChange={(e) => setForm((f) => ({ ...f, unlimitedCourses: e.target.checked }))}
                />
                {!form.unlimitedCourses && (
                  <Input
                    {...props}
                    type="number"
                    min={1}
                    value={form.maxCourses}
                    onChange={(e) => setForm((f) => ({ ...f, maxCourses: e.target.value }))}
                  />
                )}
              </div>
            )}
          </Field>

          <div className="grid grid-cols-2 gap-2">
            <Field label="Certificate Level">
              {(props) => (
                <Select
                  {...props}
                  options={CERT_LEVEL_OPTIONS}
                  value={form.certificateLevel}
                  onChange={(e) => setForm((f) => ({ ...f, certificateLevel: e.target.value as CertificateLevel }))}
                />
              )}
            </Field>
            <Field label="Tier Rank">
              {(props) => (
                <Input
                  {...props}
                  type="number"
                  min={1}
                  value={form.tierRank}
                  onChange={(e) => setForm((f) => ({ ...f, tierRank: e.target.value }))}
                />
              )}
            </Field>
          </div>

          <div className="sm:col-span-2">
            <Field label="Description">
              {(props) => (
                <Input
                  {...props}
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                />
              )}
            </Field>
          </div>

          <div className="sm:col-span-2">
            <Field label="Features / Benefits (one per line)">
              {(props) => (
                <Textarea
                  {...props}
                  rows={4}
                  value={form.featuresText}
                  onChange={(e) => setForm((f) => ({ ...f, featuresText: e.target.value }))}
                />
              )}
            </Field>
          </div>

          <div className="sm:col-span-2">
            <div className="mb-2 text-xs font-semibold text-navy-900">Assessment Access Rules</div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Checkbox
                label="Chapter Tests"
                checked={form.chapterTests}
                onChange={(e) => setForm((f) => ({ ...f, chapterTests: e.target.checked }))}
              />
              <Checkbox
                label="Module Tests"
                checked={form.moduleTests}
                onChange={(e) => setForm((f) => ({ ...f, moduleTests: e.target.checked }))}
              />
              <Checkbox
                label="Final Exam"
                checked={form.finalExam}
                onChange={(e) => setForm((f) => ({ ...f, finalExam: e.target.checked }))}
              />
              <Checkbox
                label="Proctoring"
                checked={form.proctoring}
                onChange={(e) => setForm((f) => ({ ...f, proctoring: e.target.checked }))}
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-4 sm:col-span-2">
            <Checkbox
              label="Active (visible to students)"
              checked={form.isActive}
              onChange={(e) => setForm((f) => ({ ...f, isActive: e.target.checked }))}
            />
            <Checkbox
              label="Recommended / Most Popular badge"
              checked={form.isRecommended}
              onChange={(e) => setForm((f) => ({ ...f, isRecommended: e.target.checked }))}
            />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={deletingTarget !== null}
        loading={deleting}
        options={
          deletingTarget
            ? {
                title: `Remove ${deletingTarget.name}?`,
                description:
                  "If students have active or historical purchases on this plan, it will be deactivated safely; otherwise it will be deleted.",
                confirmLabel: "Remove Plan",
                tone: "danger",
              }
            : null
        }
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeletingTarget(null)}
      />
    </>
  );
}
