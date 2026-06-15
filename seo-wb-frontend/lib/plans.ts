export const SUPPORT_PHONE = "0898604143";

export const PLAN_OPTIONS = [
  {
    value: "free",
    label: "Free",
    cards: 3,
    images: 9,
    priceRub: 0,
    description: "Dùng thử hệ thống tạo bài viết và ảnh AI.",
  },
  {
    value: "basic",
    label: "Basic",
    cards: 10,
    images: 60,
    priceRub: 3000,
    description: "Phù hợp shop nhỏ cần tạo đều sản phẩm mới.",
  },
  {
    value: "plus",
    label: "Plus",
    cards: 20,
    images: 120,
    priceRub: 5500,
    description: "Gói cân bằng cho shop đang vận hành thường xuyên.",
  },
  {
    value: "premium",
    label: "Premium",
    cards: 30,
    images: 180,
    priceRub: 8000,
    description: "Cho shop cần nhiều nội dung và ảnh sản phẩm hơn.",
  },
] as const;

export type PlanCode = (typeof PLAN_OPTIONS)[number]["value"];

export function planLabel(planType: string | null | undefined) {
  const normalized = planType === "pro" ? "plus" : planType === "agency" ? "premium" : planType;
  return PLAN_OPTIONS.find((plan) => plan.value === normalized)?.label ?? (planType || "Free");
}

export function planByCode(planType: string | null | undefined) {
  const normalized = planType === "pro" ? "plus" : planType === "agency" ? "premium" : planType;
  return PLAN_OPTIONS.find((plan) => plan.value === normalized) ?? PLAN_OPTIONS[0];
}
