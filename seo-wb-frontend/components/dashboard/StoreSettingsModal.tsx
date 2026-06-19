"use client";

import React, { useState } from "react";
import { KeyRound, Store } from "lucide-react";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { api } from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";
import { useLanguage } from "@/contexts/LanguageContext";

interface StoreItem {
  id: number;
  name: string;
}

interface StoreSettingsModalProps {
  store: StoreItem | null;
  isOpen: boolean;
  onClose: () => void;
  onSaved: (store: StoreItem) => void;
  onDeleted: (storeId: number) => void;
}

function getErrorMessage(err: unknown) {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "Unknown error";
}

export function StoreSettingsModal({ store, isOpen, onClose, onSaved, onDeleted }: StoreSettingsModalProps) {
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const { success, error } = useToast();
  const { t } = useLanguage();

  const save = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!store) return;
    const formData = new FormData(event.currentTarget);
    const nextName = String(formData.get("name") || "").trim();
    const apiKey = String(formData.get("wb_api_key") || "").trim();
    setIsSaving(true);
    try {
      const payload: { name?: string; wb_api_key?: string } = {};
      if (nextName && nextName !== store.name) payload.name = nextName;
      if (apiKey) payload.wb_api_key = apiKey;
      if (Object.keys(payload).length) {
        const updated = await api.patch(`/stores/${store.id}`, payload);
        onSaved({ id: updated.id, name: updated.name });
      }
      success(t("ssmSaved"));
      onClose();
    } catch (err: unknown) {
      error(t("ssmUpdateFailed"), getErrorMessage(err));
    } finally {
      setIsSaving(false);
    }
  };

  const deleteStore = async () => {
    if (!store) return;
    setIsDeleting(true);
    try {
      await api.delete(`/stores/${store.id}`);
      success(t("ssmDeleteQueued"));
      setIsDeleteConfirmOpen(false);
      onClose();
      onDeleted(store.id);
    } catch (err: unknown) {
      error(t("ssmDeleteFailed"), getErrorMessage(err));
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} title={t("ssmTitle")} description={store ? t("ssmStoreId").replace("{id}", String(store.id)) : undefined}>
        <form key={store?.id || "store-settings"} onSubmit={save} className="space-y-5">
          <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-zinc-800">
              <Store size={16} className="text-brand" />
              {t("ssmProfile")}
            </div>
            <Input name="name" label={t("ssmName")} defaultValue={store?.name || ""} />
          </div>

          <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-zinc-800">
              <KeyRound size={16} className="text-brand" />
              {t("ssmApi")}
            </div>
            <Input
              name="wb_api_key"
              label={t("ssmApiKey")}
              type="password"
              placeholder={t("ssmApiKeyPh")}
            />
          </div>

          <div className="rounded-xl border border-rose-200 bg-rose-50/70 p-4">
            <div className="mb-2 text-sm font-medium text-rose-700">{t("ssmDanger")}</div>
            <p className="mb-4 text-sm text-rose-600">{t("ssmDangerDesc")}</p>
            <Button
              type="button"
              variant="danger"
              onClick={() => setIsDeleteConfirmOpen(true)}
              disabled={isSaving || isDeleting}
              className="w-full sm:w-auto"
            >
              {t("ssmDeleteShop")}
            </Button>
          </div>

          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button variant="outline" onClick={onClose} disabled={isSaving || isDeleting} className="w-full sm:w-auto">
              {t("cancel")}
            </Button>
            <Button type="submit" variant="brand" isLoading={isSaving} className="w-full sm:w-auto">
              {t("ssmSaveSettings")}
            </Button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        isOpen={isDeleteConfirmOpen}
        title={t("ssmDeleteShop")}
        description={t("ssmDeleteConfirmDesc").replace("{name}", store?.name || t("store"))}
        confirmLabel={t("ssmDeleteShop")}
        isLoading={isDeleting}
        onCancel={() => setIsDeleteConfirmOpen(false)}
        onConfirm={deleteStore}
      />
    </>
  );
}
