"use client";

import React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Step {
  id: string;
  name: string;
}

interface StepperProps {
  steps: Step[];
  currentStepIndex: number;
}

export function Stepper({ steps, currentStepIndex }: StepperProps) {
  return (
    <nav aria-label="Progress" className="mb-8 w-full overflow-x-auto pb-4 custom-scrollbar">
      <ol role="list" className="flex items-center space-x-4">
        {steps.map((step, index) => {
          const isCompleted = currentStepIndex > index;
          const isCurrent = currentStepIndex === index;
          
          return (
            <li key={step.name} className="relative pr-4">
              <div className="flex items-center">
                <div
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 transition-all duration-200",
                    isCompleted
                      ? "border-brand bg-brand text-white shadow-soft-sm"
                      : isCurrent
                      ? "border-brand bg-white text-brand"
                      : "border-zinc-300 bg-white text-zinc-400"
                  )}
                >
                  {isCompleted ? (
                    <Check className="h-5 w-5" aria-hidden="true" />
                  ) : (
                    <span className={cn(
                        "text-sm font-medium",
                        (isCurrent || isCompleted) ? "text-inherit" : "text-zinc-500"
                    )}>{index + 1}</span>
                  )}
                </div>
                <span
                  className={cn(
                    "ml-3 text-sm font-medium whitespace-nowrap",
                    isCompleted ? "text-zinc-950" : isCurrent ? "text-brand" : "text-zinc-500"
                  )}
                >
                  {step.name}
                </span>
                {index !== steps.length - 1 && (
                   <div 
                     className={cn(
                        "ml-4 w-8 h-px",
                        isCompleted ? "bg-brand" : "bg-zinc-200"
                     )} 
                     aria-hidden="true" 
                   />
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
