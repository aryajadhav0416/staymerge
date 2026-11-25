import React from "react";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-500">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
        <p>
          <span className="font-semibold text-slate-700">StayMerge</span> — Multi-supplier Hotel Deduplication & Catalogue Engine.
        </p>
        <p className="inline-flex items-center gap-1.5 bg-slate-100 px-2.5 py-1 rounded-full text-slate-600 font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-teal-500" />
          Notice: All hotel listings and supplier data shown are synthetic.
        </p>
      </div>
    </footer>
  );
}

