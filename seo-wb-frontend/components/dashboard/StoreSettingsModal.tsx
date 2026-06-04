"use client";

import React, { useState } from "react";
import { KeyRound, Store } from "lucide-react";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { api } from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";

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
      success("Store settings saved");
      onClose();
    } catch (err: unknown) {
      error("Could not update store", getErrorMessage(err));
    } finally {
      setIsSaving(false);
    }
  };

  const deleteStore = async () => {
    if (!store) return;
    setIsDeleting(true);
    try {
      await api.delete(`/stores/${store.id}`);
      success("Store deletion queued");
      setIsDeleteConfirmOpen(false);
      onClose();
      onDeleted(store.id);
    } catch (err: unknown) {
      error("Could not delete store", getErrorMessage(err));
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} title="Store Settings" description={store ? `Store ID ${store.id}` : undefined}>
        <form key={store?.id || "store-settings"} onSubmit={save} className="space-y-5">
          <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-zinc-800">
              <Store size={16} className="text-brand" />
              Store profile
            </div>
            <Input name="name" label="Store Name" defaultValue={store?.name || ""} />
          </div>

          <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-zinc-800">
              <KeyRound size={16} className="text-brand" />
              Wildberries API
            </div>
            <Input
              name="wb_api_key"
              label="New Content API Key"
              type="password"
              placeholder="Leave empty to keep the current key"
            />
          </div>

          <div className="rounded-xl border border-rose-200 bg-rose-50/70 p-4">
            <div className="mb-2 text-sm font-medium text-rose-700">Danger zone</div>
            <p className="mb-4 text-sm text-rose-600">
              Deleting this shop also removes its local drafts and job history from this workspace.
            </p>
            <Button
              type="button"
              variant="danger"
              onClick={() => setIsDeleteConfirmOpen(true)}
              disabled={isSaving || isDeleting}
              className="w-full sm:w-auto"
            >
              Delete Shop
            </Button>
          </div>

          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button variant="outline" onClick={onClose} disabled={isSaving || isDeleting} className="w-full sm:w-auto">
              Cancel
            </Button>
            <Button type="submit" variant="brand" isLoading={isSaving} className="w-full sm:w-auto">
              Save Settings
            </Button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        isOpen={isDeleteConfirmOpen}
        title="Delete Shop"
        description={`"${store?.name || "This shop"}" will be permanently removed from this workspace. This action cannot be undone.`}
        confirmLabel="Delete Shop"
        isLoading={isDeleting}
        onCancel={() => setIsDeleteConfirmOpen(false)}
        onConfirm={deleteStore}
      />
    </>
  );
}
