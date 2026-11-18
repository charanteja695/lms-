import QRCode from "qrcode";
import { useEffect, useState } from "react";

import { inr } from "@/modules/billing/common/format";
import type { GatewayCheckoutPayload, StudentPaymentTransaction } from "@/modules/store/studentTypes";
import { Button, Icon } from "@/shared/ui";

function formatCountdown(expiresAt: string | null): string {
  if (!expiresAt) return "09:52";
  const diff = Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000));
  const m = String(Math.floor(diff / 60)).padStart(2, "0");
  const s = String(diff % 60).padStart(2, "0");
  return `${m}:${s}`;
}

export function UpiQrCard({
  transaction,
  checkout,
  onBack,
  onRefreshStatus,
  onSimulateSuccess,
  onSimulateFailure,
  busy,
}: {
  transaction: StudentPaymentTransaction;
  checkout: GatewayCheckoutPayload;
  onBack: () => void;
  onRefreshStatus: () => void;
  onSimulateSuccess?: () => void;
  onSimulateFailure?: () => void;
  busy?: boolean;
}) {
  const [qrDataUrl, setQrDataUrl] = useState<string>("");
  const [countdown, setCountdown] = useState<string>(() => formatCountdown(checkout.expires_at ?? transaction.expires_at));
  const payload = checkout.upi_qr_payload || transaction.upi_qr_payload || "";

  useEffect(() => {
    if (!payload) return;
    QRCode.toDataURL(payload, { width: 200, margin: 1, color: { dark: "#0f172a", light: "#ffffff" } })
      .then(setQrDataUrl)
      .catch(() => setQrDataUrl(""));
  }, [payload]);

  useEffect(() => {
    const id = setInterval(() => {
      setCountdown(formatCountdown(checkout.expires_at ?? transaction.expires_at));
    }, 1000);
    return () => clearInterval(id);
  }, [checkout.expires_at, transaction.expires_at]);

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-navy-900"
        >
          <Icon name="arrowLeft" size={14} />
          Back
        </button>
        <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-[11px] font-semibold text-brand-700">
          {transaction.transaction_ref}
        </span>
      </div>

      <div className="mt-4 flex flex-col items-center text-center">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-2 flex items-center justify-center gap-1.5 text-sm font-extrabold tracking-wide text-navy-900">
            <span className="text-orange-500">UPI</span>
            <span className="text-emerald-600">▸</span>
          </div>
          {qrDataUrl ? (
            <img src={qrDataUrl} alt="UPI Payment QR Code" className="h-44 w-44 rounded-lg" />
          ) : (
            <div className="flex h-44 w-44 items-center justify-center rounded-lg bg-slate-50 text-xs text-slate-400">
              Generating QR...
            </div>
          )}
        </div>

        <h3 className="mt-4 text-base font-bold text-navy-950">Scan QR Code to Pay</h3>
        <p className="mt-1 text-sm text-slate-600">
          Pay <strong className="text-navy-950">{inr(transaction.total_amount_paise)}</strong> using any UPI app
        </p>

        <div className="my-3 flex w-full items-center gap-3 text-xs text-slate-400">
          <div className="h-px flex-1 bg-slate-200" />
          <span>OR</span>
          <div className="h-px flex-1 bg-slate-200" />
        </div>

        {payload && (
          <a
            href={payload}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-brand-200 bg-brand-50/70 px-4 py-2.5 text-sm font-semibold text-brand-700 transition hover:bg-brand-100"
          >
            Open UPI App
            <Icon name="arrow-right" size={15} />
          </a>
        )}

        <div className="mt-3 flex items-center gap-1.5 text-xs text-slate-500">
          <Icon name="clock" size={14} />
          <span>This page will expire in <strong>{countdown}</strong></span>
        </div>

        <div className="mt-4 flex w-full flex-col gap-2 border-t border-slate-100 pt-4">
          <Button variant="secondary" onClick={onRefreshStatus} loading={busy} className="w-full">
            <Icon name="refreshCw" size={15} />
            Check Payment Status
          </Button>

          {checkout.test_mode && onSimulateSuccess && (
            <div className="mt-1 rounded-xl border border-dashed border-brand-200 bg-slate-50 p-3 text-left">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Gateway Test Mode ({checkout.provider})
              </p>
              <p className="mt-0.5 text-xs text-slate-500">
                Verifies server HMAC signature before activating your subscription.
              </p>
              <div className="mt-2.5 flex gap-2">
                <Button size="sm" variant="primary" className="flex-1" loading={busy} onClick={onSimulateSuccess}>
                  Confirm Paid (Verified)
                </Button>
                {onSimulateFailure && (
                  <Button size="sm" variant="danger" loading={busy} onClick={onSimulateFailure}>
                    Simulate Fail
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
