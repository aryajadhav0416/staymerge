import React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "danger" | "teal" | "outline";
}

export function Badge({ className, variant = "default", children, ...props }: BadgeProps) {
  const variantStyles = {
    default: "bg-slate-100 text-slate-800 border-slate-300",
    teal: "bg-teal-50 text-teal-800 border-teal-300",
    success: "bg-emerald-50 text-emerald-800 border-emerald-300",
    warning: "bg-amber-50 text-amber-900 border-amber-300",
    danger: "bg-rose-50 text-rose-800 border-rose-300",
    outline: "bg-transparent text-slate-700 border-slate-400",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border",
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}
