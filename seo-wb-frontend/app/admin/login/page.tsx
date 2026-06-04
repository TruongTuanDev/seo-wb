"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Shield } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/contexts/ToastContext";
import { api } from "@/lib/api";

const schema = z.object({
  email: z.string().email("Invalid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type FormValues = z.infer<typeof schema>;

export default function AdminLoginPage() {
  const { login } = useAuth();
  const { error } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setIsLoading(true);
    try {
      const response = await api.post("/admin/login", values, { requireAuth: false, redirectOnUnauthorized: false });
      login(response.user, "/admin", "admin");
    } catch (err) {
      error("Admin login failed", err instanceof Error ? err.message : "Invalid admin credentials");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#f7c873_0%,#f3e5c3_22%,#f8f5ef_55%,#ede7dd_100%)] px-4 py-10">
      <div className="mx-auto grid min-h-[calc(100vh-5rem)] max-w-6xl items-center gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="rounded-[36px] bg-[#1d2634] p-8 text-stone-100 shadow-2xl shadow-stone-400/30 lg:p-12">
          <div className="inline-flex rounded-full border border-amber-300/30 bg-amber-300/10 p-3 text-amber-200">
            <Shield size={24} />
          </div>
          <p className="mt-6 text-xs uppercase tracking-[0.28em] text-amber-200/80">Restricted access</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight">AI Product Studio Admin</h1>
          <p className="mt-4 max-w-xl text-base text-stone-300">
            Separate admin access for user control, model template management, usage monitoring, and AI configuration.
          </p>
        </section>

        <section className="rounded-[32px] border border-stone-200 bg-white/90 p-8 shadow-xl shadow-stone-300/30 backdrop-blur">
          <h2 className="text-2xl font-semibold tracking-tight text-stone-950">Admin login</h2>
          <p className="mt-2 text-sm text-stone-500">Only `admin` and `super_admin` accounts can sign in here.</p>
          <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-4">
            <Input label="Email" type="email" placeholder="admin@example.com" {...register("email")} error={errors.email?.message} />
            <Input label="Password" type="password" placeholder="••••••••" {...register("password")} error={errors.password?.message} />
            <Button type="submit" variant="brand" className="w-full" isLoading={isLoading}>
              Enter admin panel
            </Button>
          </form>
        </section>
      </div>
    </div>
  );
}
