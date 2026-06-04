"use client";

import { useCallback, useState } from "react";

export function useCardForm() {
  const [currentStep, setCurrentStep] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [formError, setFormError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const clearErrors = useCallback(() => {
    setFormError("");
    setFieldErrors({});
  }, []);

  return {
    currentStep,
    setCurrentStep,
    isProcessing,
    setIsProcessing,
    formError,
    setFormError,
    fieldErrors,
    setFieldErrors,
    clearErrors,
  };
}
