"use client";

import React, { useEffect, useState, useMemo, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  PageHeader,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  SearchInput,
  Select,
  Button,
  Badge,
  Skeleton,
  EmptyState,
  ErrorState,
} from "@/components/ui";
import { getCatalogue, getFeeds, HotelSummary } from "@/lib/api";
import {
  Building2,
  MapPin,
  Star,
  Tag,
  Layers,
  ArrowUpDown,
  Sparkles,
} from "lucide-react";

function CatalogueContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // URL state
  const querySearch = searchParams.get("q") || "";
  const queryCity = searchParams.get("city") || "ALL";
  const queryStars = searchParams.get("stars") || "ALL";
  const querySort = searchParams.get("sort") || "best_value";

  const [hotels, setHotels] = useState<HotelSummary[]>([]);
  const [totalRawListings, setTotalRawListings] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Local inputs
  const [searchInput, setSearchInput] = useState(querySearch);
  const [forceState, setForceState] = useState<"auto" | "empty" | "error">("auto");

  // Keep search input synced when URL changes
  useEffect(() => {
    setSearchInput(querySearch);
  }, [querySearch]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [catData, feedsData] = await Promise.all([
        getCatalogue(),
        getFeeds().catch(() => null),
      ]);
      setHotels(catData || []);

      if (feedsData && feedsData.suppliers) {
        const total = feedsData.suppliers.reduce(
          (sum, s) => sum + (s.row_count || 0),
          0
        );
        setTotalRawListings(total);
      }
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to load hotel catalogue"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Update URL helper
  const updateUrlParams = (updates: {
    q?: string;
    city?: string;
    stars?: string;
    sort?: string;
  }) => {
    const params = new URLSearchParams(searchParams.toString());

    if (updates.q !== undefined) {
      if (updates.q) params.set("q", updates.q);
      else params.delete("q");
    }
    if (updates.city !== undefined) {
      if (updates.city && updates.city !== "ALL")
        params.set("city", updates.city);
      else params.delete("city");
    }
    if (updates.stars !== undefined) {
      if (updates.stars && updates.stars !== "ALL")
        params.set("stars", updates.stars);
      else params.delete("stars");
    }
    if (updates.sort !== undefined) {
      if (updates.sort && updates.sort !== "best_value")
        params.set("sort", updates.sort);
      else params.delete("sort");
    }

    const qs = params.toString();
    router.replace(`/catalogue${qs ? `?${qs}` : ""}`, { scroll: false });
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateUrlParams({ q: searchInput });
  };

  // Derive unique cities from loaded hotels
  const cityOptions = useMemo(() => {
    const uniqueCities = Array.from(
      new Set(hotels.map((h) => h.city).filter(Boolean))
    ).sort();
    return [
      { label: "All Cities", value: "ALL" },
      ...uniqueCities.map((c) => ({ label: c, value: c })),
    ];
  }, [hotels]);

  // Filter and Sort hotels
  const filteredAndSortedHotels = useMemo(() => {
    let list = [...hotels];

    // Filter search text
    if (querySearch.trim()) {
      const term = querySearch.trim().toLowerCase();
      list = list.filter((h) => {
        const name = (h.name || "").toLowerCase();
        const addr = (h.address || "").toLowerCase();
        const city = (h.city || "").toLowerCase();
        return (
          name.includes(term) || addr.includes(term) || city.includes(term)
        );
      });
    }

    // Filter city
    if (queryCity !== "ALL") {
      list = list.filter(
        (h) => (h.city || "").toLowerCase() === queryCity.toLowerCase()
      );
    }

    // Filter star rating
    if (queryStars !== "ALL") {
      list = list.filter(
        (h) => String(h.stars || "") === String(queryStars)
      );
    }

    // Sorting
    if (querySort === "lowest_price") {
      list.sort((a, b) => {
        const priceA = a.best_offer?.price_inr ?? Infinity;
        const priceB = b.best_offer?.price_inr ?? Infinity;
        return priceA - priceB;
      });
    } else if (querySort === "most_offers") {
      list.sort((a, b) => (b.offers?.length || 0) - (a.offers?.length || 0));
    }
    // "best_value" defaults to cluster order from catalogue.json

    return list;
  }, [hotels, querySearch, queryCity, queryStars, querySort]);

  // Extract locality from address (e.g., first segment or last clean token)
  const formatLocality = (address: string, city: string) => {
    if (!address) return city;
    const parts = address.split(",").map((p) => p.trim());
    return parts[parts.length - 1] || parts[0] || city;
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hotel Catalogue"
        description="Consolidated master hotel records deduplicated across supplier feeds, with the best value offer highlighted."
        badge={<Badge variant="teal">{hotels.length} Master Hotels</Badge>}
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

      {/* Summary Line: Number of Hotels & Raw Listings */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-xl border border-teal-100 bg-teal-50/40 gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-teal-600 text-white flex items-center justify-center shrink-0 shadow-xs">
            <Building2 className="w-5 h-5" />
          </div>
          <div>
            <div className="text-sm font-bold text-slate-900">
              {loading ? (
                <Skeleton className="h-5 w-40" />
              ) : (
                <span>
                  <strong>{filteredAndSortedHotels.length}</strong> {filteredAndSortedHotels.length === 1 ? "Hotel" : "Hotels"} Displayed
                  {hotels.length !== filteredAndSortedHotels.length && (
                    <span className="text-slate-500 font-normal"> (filtered from {hotels.length})</span>
                  )}
                </span>
              )}
            </div>
            <div className="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
              <Layers className="w-3.5 h-3.5 text-teal-600" />
              <span>
                Consolidated from{" "}
                <strong className="text-slate-800">
                  {totalRawListings !== null ? `${totalRawListings} raw listings` : "298 raw listings"}
                </strong>{" "}
                across 3 suppliers (A, B, C)
              </span>
            </div>
          </div>
        </div>

        <div className="text-xs text-teal-800 font-semibold bg-white/80 px-3 py-1.5 rounded-lg border border-teal-200/60 shadow-2xs self-start sm:self-auto">
          Deduplication ratio: ~{( (totalRawListings || 298) / (hotels.length || 1) ).toFixed(2)}x
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card>
        <CardContent className="p-4">
          <form onSubmit={handleSearchSubmit} className="flex flex-col lg:flex-row gap-3 items-center">
            {/* Search Box */}
            <div className="flex-1 w-full">
              <SearchInput
                placeholder="Search hotel name, locality, or city..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </div>

            {/* City Filter */}
            <div className="w-full lg:w-44">
              <Select
                value={queryCity}
                onChange={(e) => updateUrlParams({ city: e.target.value })}
                options={cityOptions}
              />
            </div>

            {/* Star Rating Filter */}
            <div className="w-full lg:w-36">
              <Select
                value={queryStars}
                onChange={(e) => updateUrlParams({ stars: e.target.value })}
                options={[
                  { label: "All Stars", value: "ALL" },
                  { label: "5 Stars ★★★★★", value: "5" },
                  { label: "4 Stars ★★★★", value: "4" },
                  { label: "3 Stars ★★★", value: "3" },
                  { label: "2 Stars ★★", value: "2" },
                ]}
              />
            </div>

            {/* Sort Dropdown */}
            <div className="w-full lg:w-44">
              <Select
                value={querySort}
                onChange={(e) => updateUrlParams({ sort: e.target.value })}
                options={[
                  { label: "Sort: Best Value", value: "best_value" },
                  { label: "Sort: Lowest Price", value: "lowest_price" },
                  { label: "Sort: Most Offers", value: "most_offers" },
                ]}
              />
            </div>

            <Button type="submit">Filter</Button>

            {/* Reset Button */}
            {(querySearch || queryCity !== "ALL" || queryStars !== "ALL" || querySort !== "best_value") && (
              <Button
                variant="outline"
                type="button"
                onClick={() => {
                  setSearchInput("");
                  updateUrlParams({ q: "", city: "ALL", stars: "ALL", sort: "best_value" });
                }}
              >
                Reset
              </Button>
            )}
          </form>
        </CardContent>
      </Card>

      {/* Content States */}
      {forceState === "empty" || (!loading && filteredAndSortedHotels.length === 0 && !error) ? (
        <EmptyState
          title="No Hotels Match Filters"
          description="Try broadening your search keyword, selecting a different city, or resetting star rating."
          action={
            <Button
              variant="outline"
              onClick={() => {
                setSearchInput("");
                updateUrlParams({ q: "", city: "ALL", stars: "ALL", sort: "best_value" });
                setForceState("auto");
              }}
            >
              Clear Filters
            </Button>
          }
        />
      ) : forceState === "error" || error ? (
        <ErrorState
          title="Failed to Load Catalogue"
          message={error || "Could not retrieve master hotel catalogue from backend."}
          onRetry={loadData}
        />
      ) : loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="flex flex-col justify-between h-64 p-5 space-y-4">
              <div className="space-y-3">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-6 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
              </div>
              <Skeleton className="h-16 w-full rounded-lg" />
              <div className="flex justify-between items-center pt-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-16" />
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredAndSortedHotels.map((hotel) => (
            <Link
              key={hotel.cluster_id}
              href={`/hotels/${hotel.cluster_id}`}
              className="block group focus:outline-none"
            >
              <Card
                hoverable
                className="h-full flex flex-col justify-between transition-all duration-200 group-hover:border-teal-500 group-hover:shadow-md border-slate-200 bg-white"
              >
                <div>
                  <CardHeader className="pb-3 border-b border-slate-100">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <span className="text-[11px] font-mono text-teal-700 bg-teal-50 px-2 py-0.5 rounded font-semibold">
                          {hotel.cluster_id}
                        </span>
                        <CardTitle className="text-base text-slate-900 mt-1 line-clamp-1 group-hover:text-teal-700 transition-colors">
                          {hotel.name}
                        </CardTitle>
                      </div>

                      {hotel.stars && (
                        <div className="flex items-center gap-1 text-amber-500 bg-amber-50 px-2 py-0.5 rounded text-xs font-bold shrink-0">
                          <Star className="w-3.5 h-3.5 fill-amber-400" />
                          <span>{hotel.stars}★</span>
                        </div>
                      )}
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-3 pt-3">
                    {/* Locality and City */}
                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                      <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span className="truncate">
                        {hotel.address ? `${hotel.address}, ` : ""}
                        <strong>{hotel.city}</strong>
                      </span>
                    </div>

                    {/* Best-Offer Badge with Price & Short Reason */}
                    {hotel.best_offer && (
                      <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-lg space-y-1 group-hover:bg-teal-50/30 group-hover:border-teal-200 transition-colors">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold text-teal-800 uppercase tracking-wider inline-flex items-center gap-1">
                            <Tag className="w-3 h-3 text-teal-600" /> Best Offer
                          </span>
                          <span className="text-sm font-extrabold text-slate-900">
                            Rs {Number(hotel.best_offer.price_inr || 0).toLocaleString()}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-600 italic line-clamp-2 leading-relaxed">
                          {hotel.best_offer_reason || "Selected optimal value offer across supplier feeds."}
                        </p>
                      </div>
                    )}
                  </CardContent>
                </div>

                {/* Footer: Supplier Offers Count and CTA */}
                <div className="py-3 px-6 bg-slate-50/60 border-t border-slate-100 flex items-center justify-between text-xs">
                  <span className="text-slate-500 font-medium">
                    <strong className="text-slate-800">{hotel.offers?.length || 1}</strong>{" "}
                    {hotel.offers?.length === 1 ? "supplier offer" : "supplier offers"}
                  </span>
                  <span className="text-teal-600 font-semibold group-hover:translate-x-0.5 transition-transform inline-flex items-center gap-1">
                    View details &rarr;
                  </span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CataloguePage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <CatalogueContent />
    </Suspense>
  );
}
