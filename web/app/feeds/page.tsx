"use client";

import React, { useEffect, useState, useMemo, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  PageHeader,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  SearchInput,
  Select,
  Button,
  Badge,
  Skeleton,
  EmptyState,
  ErrorState,
} from "@/components/ui";
import { getFeeds, SupplierFeed, SupplierRow } from "@/lib/api";
import {
  Database,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Star,
} from "lucide-react";

const PAGE_SIZE = 20;

function FeedsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Query state from URL
  const querySupplier = searchParams.get("supplier") || "ALL";
  const querySearch = searchParams.get("q") || "";
  const queryPage = parseInt(searchParams.get("page") || "1", 10);

  const [suppliers, setSuppliers] = useState<SupplierFeed[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Local inputs synced to URL
  const [searchInput, setSearchInput] = useState(querySearch);
  const [activeTab, setActiveTab] = useState<string>(
    querySupplier === "ALL" ? "A" : querySupplier
  );
  const [forceState, setForceState] = useState<"auto" | "empty" | "error">("auto");

  // Keep search input in sync if URL changes
  useEffect(() => {
    setSearchInput(querySearch);
  }, [querySearch]);

  const loadFeeds = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getFeeds();
      setSuppliers(res.suppliers || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load supplier feeds");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFeeds();
  }, []);

  // Update URL helper
  const updateUrlParams = (updates: {
    q?: string;
    supplier?: string;
    page?: number;
  }) => {
    const params = new URLSearchParams(searchParams.toString());

    if (updates.q !== undefined) {
      if (updates.q) params.set("q", updates.q);
      else params.delete("q");
    }
    if (updates.supplier !== undefined) {
      if (updates.supplier && updates.supplier !== "ALL")
        params.set("supplier", updates.supplier);
      else params.delete("supplier");
    }
    if (updates.page !== undefined) {
      if (updates.page > 1) params.set("page", updates.page.toString());
      else params.delete("page");
    }

    const qs = params.toString();
    router.replace(`/feeds${qs ? `?${qs}` : ""}`, { scroll: false });
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateUrlParams({ q: searchInput, page: 1 });
  };

  const handleSupplierChange = (sup: string) => {
    updateUrlParams({ supplier: sup, page: 1 });
    if (sup !== "ALL") {
      setActiveTab(sup);
    }
  };

  // Helper to filter rows for a supplier feed
  const filterRows = (rows: SupplierRow[] = []) => {
    if (!querySearch.trim()) return rows;
    const term = querySearch.trim().toLowerCase();
    return rows.filter((r) => {
      const name = (r.name || "").toLowerCase();
      const addr = (r.address || "").toLowerCase();
      const city = (r.city || "").toLowerCase();
      return name.includes(term) || addr.includes(term) || city.includes(term);
    });
  };

  // Filtered suppliers data
  const filteredSuppliers = useMemo(() => {
    return suppliers.map((sup) => {
      const allRows = sup.rows || [];
      const matched = filterRows(allRows);
      return {
        ...sup,
        filteredRows: matched,
        totalMatched: matched.length,
      };
    });
  }, [suppliers, querySearch]);

  // Active supplier list to display based on supplier filter
  const visibleSuppliers = useMemo(() => {
    if (querySupplier === "ALL") {
      return filteredSuppliers;
    }
    return filteredSuppliers.filter((s) => s.supplier === querySupplier);
  }, [filteredSuppliers, querySupplier]);

  const activeMobileSupplier = useMemo(() => {
    return (
      filteredSuppliers.find((s) => s.supplier === activeTab) ||
      filteredSuppliers[0]
    );
  }, [filteredSuppliers, activeTab]);

  // Pagination for each supplier
  const paginatedSupplierRows = (rows: SupplierRow[] = []) => {
    const start = (queryPage - 1) * PAGE_SIZE;
    return rows.slice(start, start + PAGE_SIZE);
  };

  const maxTotalRows = useMemo(() => {
    if (visibleSuppliers.length === 0) return 0;
    return Math.max(...visibleSuppliers.map((s) => s.filteredRows.length));
  }, [visibleSuppliers]);

  const totalPages = Math.max(1, Math.ceil(maxTotalRows / PAGE_SIZE));

  const formatMissing = (val: any) => {
    if (val === null || val === undefined || val === "" || String(val).toLowerCase() === "nan") {
      return <span className="text-slate-300 font-bold select-none">&mdash;</span>;
    }
    return String(val);
  };

  const renderSupplierTable = (sup: typeof filteredSuppliers[0]) => {
    const pageRows = paginatedSupplierRows(sup.filteredRows);

    return (
      <Card key={sup.supplier} className="flex-1 flex flex-col justify-between shadow-xs border-slate-200">
        <div>
          <CardHeader className="py-3 px-4 bg-slate-50/70 border-b border-slate-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CardTitle className="text-sm font-bold text-slate-900">
                  {sup.name}
                </CardTitle>
                <Badge variant="teal">Code: {sup.supplier}</Badge>
              </div>
              <Badge variant="outline" className="font-semibold text-xs">
                {sup.filteredRows.length} {sup.filteredRows.length === 1 ? "row" : "rows"}
              </Badge>
            </div>
          </CardHeader>

          <CardContent className="p-0">
            <Table className="border-0 rounded-none text-xs">
              <TableHeader>
                <TableRow className="bg-slate-50/50 text-[11px]">
                  <TableHead className="py-2.5 px-3">Name</TableHead>
                  <TableHead className="py-2.5 px-3">Address</TableHead>
                  <TableHead className="py-2.5 px-2">City</TableHead>
                  <TableHead className="py-2.5 px-2">Pincode</TableHead>
                  <TableHead className="py-2.5 px-2">Stars</TableHead>
                  <TableHead className="py-2.5 px-3 text-right">Price</TableHead>
                  <TableHead className="py-2.5 px-3">Policy</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageRows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-8 text-slate-400">
                      No matching records for {sup.name}
                    </TableCell>
                  </TableRow>
                ) : (
                  pageRows.map((row) => (
                    <TableRow key={row.row_id} className="hover:bg-slate-50/80">
                      <TableCell className="py-2.5 px-3 font-medium text-slate-900 max-w-[150px] truncate" title={row.name || ""}>
                        {formatMissing(row.name)}
                      </TableCell>
                      <TableCell className="py-2.5 px-3 text-slate-600 max-w-[140px] truncate" title={row.address || ""}>
                        {formatMissing(row.address)}
                      </TableCell>
                      <TableCell className="py-2.5 px-2 text-slate-700 whitespace-nowrap">
                        {formatMissing(row.city)}
                      </TableCell>
                      <TableCell className="py-2.5 px-2 font-mono text-[11px] text-slate-500 whitespace-nowrap">
                        {formatMissing(row.pincode)}
                      </TableCell>
                      <TableCell className="py-2.5 px-2 whitespace-nowrap">
                        {row.stars ? (
                          <span className="inline-flex items-center gap-0.5 text-amber-500 font-semibold text-[11px]">
                            {row.stars}★
                          </span>
                        ) : (
                          formatMissing(null)
                        )}
                      </TableCell>
                      <TableCell className="py-2.5 px-3 text-right font-semibold text-slate-900 whitespace-nowrap">
                        {row.price_inr ? `₹${Number(row.price_inr).toLocaleString()}` : formatMissing(null)}
                      </TableCell>
                      <TableCell className="py-2.5 px-3 text-slate-500 text-[11px] max-w-[110px] truncate" title={row.cancellation_policy || ""}>
                        {formatMissing(row.cancellation_policy)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </div>

        <div className="py-2.5 px-4 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
          <span>Reliability: <strong>{(sup.reliability * 100).toFixed(0)}%</strong></span>
          <span>Showing {pageRows.length} of {sup.filteredRows.length}</span>
        </div>
      </Card>
    );
  };

  const totalFilteredCount = useMemo(() => {
    return filteredSuppliers.reduce((acc, s) => acc + s.filteredRows.length, 0);
  }, [filteredSuppliers]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Supplier Feeds"
        description="Inspect raw incoming feeds from suppliers A, B, and C with noisy names, missing pincodes, and unparsed fields."
        badge={
          <div className="flex items-center gap-1.5 flex-wrap">
            {suppliers.map((s) => (
              <Badge key={s.supplier} variant="teal">
                Supplier {s.supplier}: {s.row_count}
              </Badge>
            ))}
          </div>
        }
        actions={
          <div className="flex items-center gap-2 bg-slate-100 p-1 rounded-lg">
            {(["auto", "empty", "error"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setForceState(s)}
                className={`px-2.5 py-1 rounded text-xs font-medium capitalize transition-all ${
                  forceState === s
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {s === "auto" ? "Live Data" : s}
              </button>
            ))}
          </div>
        }
      />

      {/* Search and Filter Controls */}
      <Card>
        <CardContent className="p-4">
          <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1">
              <SearchInput
                placeholder="Search hotel name, address, or city..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </div>

            <div className="w-full sm:w-48">
              <Select
                value={querySupplier}
                onChange={(e) => handleSupplierChange(e.target.value)}
                options={[
                  { label: "All Suppliers", value: "ALL" },
                  { label: "Supplier A Only", value: "A" },
                  { label: "Supplier B Only", value: "B" },
                  { label: "Supplier C Only", value: "C" },
                ]}
              />
            </div>

            <Button type="submit">Filter</Button>

            {(querySearch || querySupplier !== "ALL") && (
              <Button
                variant="outline"
                type="button"
                onClick={() => {
                  setSearchInput("");
                  updateUrlParams({ q: "", supplier: "ALL", page: 1 });
                }}
              >
                Reset
              </Button>
            )}
          </form>
        </CardContent>
      </Card>

      {/* Content States */}
      {forceState === "empty" || (!loading && totalFilteredCount === 0 && !error) ? (
        <EmptyState
          title="No Supplier Rows Found"
          description="No records match your search criteria across the supplier feeds."
          action={
            <Button
              variant="outline"
              onClick={() => {
                setSearchInput("");
                updateUrlParams({ q: "", supplier: "ALL", page: 1 });
                setForceState("auto");
              }}
            >
              Clear Filters
            </Button>
          }
        />
      ) : forceState === "error" || error ? (
        <ErrorState
          title="Supplier Feeds Unavailable"
          message={error || "Could not retrieve supplier feeds data."}
          onRetry={loadFeeds}
        />
      ) : loading ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Skeleton className="h-96 w-full" />
            <Skeleton className="h-96 w-full" />
            <Skeleton className="h-96 w-full" />
          </div>
        </div>
      ) : (
        <>
          {/* Mobile Tabs: visible only on small screens (<lg) */}
          <div className="block lg:hidden space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
              {filteredSuppliers.map((sup) => (
                <button
                  key={sup.supplier}
                  onClick={() => setActiveTab(sup.supplier)}
                  className={`flex-1 py-2 px-3 text-xs font-semibold rounded-lg flex items-center justify-center gap-1.5 transition-all ${
                    activeTab === sup.supplier
                      ? "bg-teal-600 text-white shadow-xs"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  <span>{sup.name}</span>
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                    activeTab === sup.supplier ? "bg-teal-800 text-teal-100" : "bg-slate-200 text-slate-600"
                  }`}>
                    {sup.filteredRows.length}
                  </span>
                </button>
              ))}
            </div>

            {activeMobileSupplier && renderSupplierTable(activeMobileSupplier)}
          </div>

          {/* Wide Screen: Side-by-Side (>=lg) */}
          <div className="hidden lg:grid grid-cols-3 gap-6 items-start">
            {visibleSuppliers.map((sup) => renderSupplierTable(sup))}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-200 pt-4 px-2">
              <span className="text-xs text-slate-500">
                Page <strong>{queryPage}</strong> of <strong>{totalPages}</strong> (20 rows/page)
              </span>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={queryPage <= 1}
                  onClick={() => updateUrlParams({ page: queryPage - 1 })}
                  className="gap-1 text-xs"
                >
                  <ChevronLeft className="w-3.5 h-3.5" /> Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={queryPage >= totalPages}
                  onClick={() => updateUrlParams({ page: queryPage + 1 })}
                  className="gap-1 text-xs"
                >
                  Next <ChevronRight className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function FeedsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <FeedsContent />
    </Suspense>
  );
}
