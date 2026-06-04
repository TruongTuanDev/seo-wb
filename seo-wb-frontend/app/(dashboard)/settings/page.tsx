"use client";

import React, { useEffect, useState } from "react";
import { KeyRound, User } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useToast } from "@/contexts/ToastContext";
import { api } from "@/lib/api";

type UsageSummary = {
  plan_type: string;
  monthly_quota: number;
  used_quota: number;
  remaining_quota: number;
  quota_percent: number;
  monthly_cost_limit: number | null;
  used_cost: number;
  remaining_cost: number | null;
  cost_percent: number | null;
  max_images_per_job: number;
  allow_legacy_vton: boolean;
  allow_gpt_image: boolean;
  priority_queue: boolean;
  credit_balance: number;
  credits_used: number;
  credits_granted: number;
  quota_reset_at: string | null;
  last_quota_reset_at: string | null;
};

export default function SettingsPage() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const { success, error } = useToast();

  const [name, setName] = useState(user?.name ?? "");
  const [savingProfile, setSavingProfile] = useState(false);

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwError, setPwError] = useState("");
  const [savingPw, setSavingPw] = useState(false);
  const [usage, setUsage] = useState<UsageSummary | null>(null);

  useEffect(() => {
    api.get("/auth/usage")
      .then((response) => setUsage(response as UsageSummary))
      .catch(() => setUsage(null));
  }, []);

  const handleSaveProfile = async () => {
    setSavingProfile(true);
    try {
      await api.patch("/auth/me", { name });
      success(t("profileUpdated"));
    } catch (err) {
      error(t("error"), err instanceof Error ? err.message : "Failed to update profile");
    } finally {
      setSavingProfile(false);
    }
  };

  const handleChangePassword = async () => {
    setPwError("");
    if (newPw !== confirmPw) {
      setPwError(t("passwordMismatch"));
      return;
    }
    setSavingPw(true);
    try {
      await api.post("/auth/change-password", {
        current_password: currentPw,
        new_password: newPw,
      });
      success(t("passwordChanged"));
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
    } catch (err) {
      error(t("error"), err instanceof Error ? err.message : "Failed to change password");
    } finally {
      setSavingPw(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight text-zinc-950">{t("accountSettings")}</h1>

      {/* Profile section */}
      <div className="mb-5 rounded-2xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-50">
            <User size={18} className="text-indigo-600" />
          </div>
          <h2 className="text-sm font-semibold text-zinc-950">{t("profile")}</h2>
        </div>

        <div className="space-y-4">
          <Input
            label={t("name")}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            label={t("email")}
            value={user?.email ?? ""}
            disabled
            className="cursor-not-allowed opacity-60"
          />
        </div>

        <div className="mt-5 flex justify-end">
          <Button variant="brand" isLoading={savingProfile} onClick={handleSaveProfile}>
            {t("saveChanges")}
          </Button>
        </div>
      </div>

      <div className="mb-5 rounded-2xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50">
              <User size={18} className="text-emerald-600" />
            </div>
            <h2 className="text-sm font-semibold text-zinc-950">Usage limits</h2>
        </div>

        {usage ? (
          <div className="space-y-5">
            <div className="rounded-2xl border border-zinc-200 bg-zinc-50 px-4 py-3">
              <div className="flex items-center justify-between gap-3 text-sm text-zinc-700">
                <span>Current plan</span>
                <span className="font-semibold uppercase text-zinc-950">{usage.plan_type}</span>
              </div>
              <p className="mt-2 text-xs text-zinc-500">
                Max images/job: {usage.max_images_per_job}. GPT image: {usage.allow_gpt_image ? "enabled" : "disabled"}. Legacy VTON: {usage.allow_legacy_vton ? "enabled" : "disabled"}.
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                Next reset: {usage.quota_reset_at ? new Date(usage.quota_reset_at).toLocaleDateString() : "Not scheduled"}
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                Credits available: {usage.credit_balance}. Credits used this cycle: {usage.credits_used}.
              </p>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between text-sm text-zinc-700">
                <span>Image quota</span>
                <span>{usage.used_quota} / {usage.monthly_quota}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-zinc-200">
                <div className="h-full rounded-full bg-emerald-500" style={{ width: `${Math.min(100, usage.quota_percent)}%` }} />
              </div>
              <p className="mt-2 text-xs text-zinc-500">Remaining this cycle: {usage.remaining_quota} images</p>
              {usage.monthly_quota > 0 && usage.used_quota / usage.monthly_quota >= 0.8 && usage.used_quota < usage.monthly_quota && (
                <p className="mt-2 text-xs font-medium text-amber-600">You are close to your monthly image limit.</p>
              )}
              {usage.monthly_quota > 0 && usage.used_quota >= usage.monthly_quota && (
                <p className="mt-2 text-xs font-medium text-rose-600">Upgrade plan or contact admin.</p>
              )}
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between text-sm text-zinc-700">
                <span>Estimated AI cost</span>
                <span>
                  ${usage.used_cost.toFixed(2)} / {usage.monthly_cost_limit === null ? "Unlimited" : `$${usage.monthly_cost_limit.toFixed(2)}`}
                </span>
              </div>
              {usage.monthly_cost_limit !== null ? (
                <>
                  <div className="h-2 overflow-hidden rounded-full bg-zinc-200">
                    <div className="h-full rounded-full bg-indigo-500" style={{ width: `${Math.min(100, usage.cost_percent ?? 0)}%` }} />
                  </div>
                  <p className="mt-2 text-xs text-zinc-500">Remaining estimated cost: ${Number(usage.remaining_cost || 0).toFixed(2)}</p>
                  {usage.cost_percent !== null && usage.cost_percent >= 80 && usage.used_cost < (usage.monthly_cost_limit ?? 0) && (
                    <p className="mt-2 text-xs font-medium text-amber-600">You are close to your monthly cost limit.</p>
                  )}
                  {usage.monthly_cost_limit !== null && usage.used_cost >= usage.monthly_cost_limit && (
                    <p className="mt-2 text-xs font-medium text-rose-600">Upgrade plan or contact admin.</p>
                  )}
                </>
              ) : (
                <p className="text-xs text-zinc-500">No cost cap has been applied to your account.</p>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-zinc-500">Usage information is unavailable right now.</p>
        )}
      </div>

      {/* Password section */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-50">
            <KeyRound size={18} className="text-amber-600" />
          </div>
          <h2 className="text-sm font-semibold text-zinc-950">{t("changePassword")}</h2>
        </div>

        <div className="space-y-4">
          <Input
            label={t("currentPassword")}
            type="password"
            value={currentPw}
            onChange={(e) => setCurrentPw(e.target.value)}
          />
          <Input
            label={t("newPassword")}
            type="password"
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
          />
          <Input
            label={t("confirmPassword")}
            type="password"
            value={confirmPw}
            onChange={(e) => setConfirmPw(e.target.value)}
            error={pwError}
          />
        </div>

        <div className="mt-5 flex justify-end">
          <Button variant="brand" isLoading={savingPw} onClick={handleChangePassword}>
            {t("changePassword")}
          </Button>
        </div>
      </div>
    </div>
  );
}
