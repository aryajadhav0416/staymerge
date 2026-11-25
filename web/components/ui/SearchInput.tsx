import React from "react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SearchInputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  onClear?: () => void;
}

export const SearchInput = React.forwardRef<HTMLInputElement, SearchInputProps>(
  ({ className, value, "aria-label": ariaLabel, placeholder, ...props }, ref) => {
    return (
      <div className="relative w-full">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none" aria-hidden="true" />
        <input
          ref={ref}
          type="text"
          value={value}
          aria-label={ariaLabel || (typeof placeholder === "string" ? placeholder : "Search")}
          placeholder={placeholder}
          className={cn(
            "w-full h-10 pl-9 pr-4 rounded-lg border border-slate-300 bg-white text-sm text-slate-900 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-teal-600 transition-all",
            className
          )}
          {...props}
        />
      </div>
    );
  }
);
SearchInput.displayName = "SearchInput";
