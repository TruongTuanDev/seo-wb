"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";

const storeSchema = z.object({
  name: z.string().min(1, "Store name is required"),
  wb_api_key: z.string().min(10, "Valid WB Content API Key is required"),
});

type StoreFormValues = z.infer<typeof storeSchema>;

function getErrorMessage(err: unknown) {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "Unknown error";
}

interface StoreItem {
  id: number;
  name: string;
}

interface CreateStoreModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (store: StoreItem) => void;
}

export function CreateStoreModal({ isOpen, onClose, onSuccess }: CreateStoreModalProps) {
  const { success, error } = useToast();
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<StoreFormValues>({
    resolver: zodResolver(storeSchema),
  });

  const onSubmit = async (data: StoreFormValues) => {
    setIsLoading(true);
    try {
      const newStore = await api.post("/stores", data) as StoreItem;
      success("Store created successfully");
      reset();
      onSuccess(newStore);
      onClose();
    } catch (err: unknown) {
      error("Failed to create store", getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal 
      isOpen={isOpen} 
      onClose={() => {
        reset();
        onClose();
      }} 
      title="Add New Store"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="Store Name"
          placeholder="e.g. FORMELA Official"
          {...register("name")}
          error={errors.name?.message}
        />
        <div className="space-y-1 my-2">
            <Input
            label="Wildberries Content API Key"
            type="password"
            placeholder="Type or paste your API key here"
            {...register("wb_api_key")}
            error={errors.wb_api_key?.message}
            />
        </div>
        

        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button type="button" variant="ghost" onClick={onClose} className="w-full sm:w-auto">
            Cancel
          </Button>
          <Button type="submit" variant="brand" isLoading={isLoading} className="w-full sm:w-auto">
            Connect Store
          </Button>
        </div>
      </form>
    </Modal>
  );
}
