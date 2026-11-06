import QRCode from "qrcode";
import { cleanOtp } from "@/core/lib/otp";
import { useEffect, useState } from "react";
import { FormProvider, useForm } from "react-hook-form";

import { toApiError } from "@/core/lib/apiError";
import { useEnableMfaMutation } from "@/modules/user-management/auth/api/authApi";
import { TextField } from "@/shared/form";
import { Alert, Button } from "@/shared/ui";

export function ScanStep({ secret, uri, onEnabled }: { secret: string; uri: string; onEnabled: (codes: string[]) => void }) {
  const [qr, setQr] = useState<string | null>(null);
  const [enable, { isLoading }] = useEnableMfaMutation();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<{ code: string }>({ defaultValues: { code: "123456" } });

  useEffect(() => {
    void QRCode.toDataURL(uri, { margin: 1, width: 200 }).then(setQr);
  }, [uri]);

  const onSubmit = form.handleSubmit(async ({ code }) => {
    setError(null);
    try {
      onEnabled(await enable({ code: cleanOtp(code) }).unwrap());
    } catch (caught) {
      setError(toApiError(caught).message);
      form.reset();
    }
  });

  return (
    <div className="grid gap-6 md:grid-cols-[220px_1fr]">
      <div className="space-y-2">
        {qr ? <img src={qr} alt="QR code for your authenticator app" className="h-[200px] w-[200px] rounded-lg border border-slate-200" /> : <div className="h-[200px] w-[200px] animate-pulse rounded-lg bg-slate-100" />}
        <p className="text-xs text-slate-500">Can't scan? Enter this key:</p>
        <code className="block break-all rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-800">{secret}</code>
      </div>
      <FormProvider {...form}>
        <form onSubmit={onSubmit} className="max-w-sm space-y-4" noValidate>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-600">
            <li>Scan the QR code with your authenticator app.</li>
            <li>Enter the 6-digit code it shows.</li>
          </ol>
          {error && <Alert tone="error">{error}</Alert>}
          <TextField name="code" label="Authentication code" inputMode="numeric" autoComplete="one-time-code" maxLength={7} placeholder="6-digit code" required />
          <Button type="submit" loading={isLoading}>
            Turn on two-factor authentication
          </Button>
        </form>
      </FormProvider>
    </div>
  );
}
