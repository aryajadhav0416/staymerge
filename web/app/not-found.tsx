import React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Hotel, ArrowLeft, Search } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4">
      <div className="w-16 h-16 rounded-2xl bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-600 mb-6 shadow-sm">
        <Hotel className="w-8 h-8" />
      </div>
      <span className="text-xs font-bold uppercase tracking-widest text-teal-700 bg-teal-50 px-3 py-1 rounded-full mb-3 border border-teal-200/60">
        404 Page Not Found
      </span>
      <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight mb-3">
        We couldn&apos;t find this page
      </h1>
      <p className="text-sm text-slate-600 max-w-md mb-8 leading-relaxed">
        The page or hotel cluster you requested does not exist or may have been reorganized during deduplication.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link href="/">
          <Button variant="outline" className="gap-2">
            <ArrowLeft className="w-4 h-4" />
            Back to Home
          </Button>
        </Link>
        <Link href="/catalogue">
          <Button variant="primary" className="gap-2">
            <Search className="w-4 h-4" />
            Explore Hotel Catalogue
          </Button>
        </Link>
      </div>
    </div>
  );
}

