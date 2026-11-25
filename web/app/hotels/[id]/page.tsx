"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
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
  Badge,
  Button,
  Skeleton,
  EmptyState,
  ErrorState,
} from "@/components/ui";
import {
  getHotelDetail,
  getDecisions,
  getFeeds,
  HotelDetail,
  Decision,
  SupplierRow,
  Offer,
} from "@/lib/api";
import {
  MapPin,
  Star,
  Tag,
  ArrowLeft,
  AlertTriangle,
  GitMerge,
  ShieldCheck,
  CheckCircle2,
  HelpCircle,
  Building2,
  Layers,
} from "lucide-react";

// Weights matching P7 value_score calculation:
// - price 0.45: min_price / price
// - cancellation 0.25: free 48h = 1.0, free 24h = 0.8, partial refund = 0.5, non-refundable = 0.1
// - payment terms 0.10: pay at hotel = 1.0, pay later = 0.7, pay now = 0.4
// - supplier reliability 0.20
function calculateValueScore(offer: Offer, allOffers: Offer[]): number {
  if (!allOffers || allOffers.length === 0) return 0;
  const validPrices = allOffers
    .map((o) => o.price_inr)
    .filter((p) => p !== undefined && p !== null && !isNaN(p) && p > 0);
  const minPrice = validPrices.length > 0 ? Math.min(...validPrices) : 0;

  // 1. Price score
  const price = offer.price_inr || 0;
  const priceScore = price > 0 && minPrice > 0 ? minPrice / price : price === 0 ? 1 : 0;

  // 2. Cancellation score
  const canc = (offer.cancellation_policy || "").toLowerCase();
  let cancScore = 0.5;
  if (canc.includes("48")) cancScore = 1.0;
  else if (canc.includes("24")) cancScore = 0.8;
  else if (canc.includes("partial")) cancScore = 0.5;
  else if (canc.includes("non")) cancScore = 0.1;

  // 3. Payment score
  const pay = (offer.payment_terms || "").toLowerCase();
  let payScore = 0.4;
  if (pay.includes("hotel")) payScore = 1.0;
  else if (pay.includes("later") || pay.includes("deposit")) payScore = 0.7;

  // 4. Reliability score
  const relScore = offer.reliability ?? 1.0;

  return 0.45 * priceScore + 0.25 * cancScore + 0.10 * payScore + 0.20 * relScore;
}

export default function HotelDetailPage() {
  const params = useParams();
  const hotelId = (params?.id as string) || "C0001";

  const [hotel, setHotel] = useState<HotelDetail | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [rawSupplierRows, setRawSupplierRows] = useState<Record<string, SupplierRow>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [forceState, setForceState] = useState<"auto" | "empty" | "error">("auto");

  const loadData = async () => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      // Parallel fetch of hotel detail, decisions log, and raw supplier feeds
      const [hotelData, decisionsData, feedsData] = await Promise.all([
        getHotelDetail(hotelId),
        getDecisions().catch(() => [] as Decision[]),
        getFeeds().catch(() => null),
      ]);

      setHotel(hotelData);
      setDecisions(decisionsData || []);

      if (feedsData && feedsData.suppliers) {
        const rowMap: Record<string, SupplierRow> = {};
        for (const sup of feedsData.suppliers) {
          if (sup.rows) {
            for (const r of sup.rows) {
              rowMap[r.row_id] = r;
            }
          }
        }
        setRawSupplierRows(rowMap);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("404") || msg.toLowerCase().includes("not found")) {
        setNotFound(true);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [hotelId]);

  // Offers sorted by value score descending
  const sortedOffers = useMemo(() => {
    if (!hotel || !hotel.offers) return [];
    return [...hotel.offers]
      .map((offer) => ({
        ...offer,
        value_score: calculateValueScore(offer, hotel.offers),
      }))
      .sort((a, b) => b.value_score - a.value_score);
  }, [hotel]);

  // Merge decisions for rows inside this cluster
  const clusterRowIds = useMemo(() => {
    if (!hotel || !hotel.offers) return new Set<string>();
    return new Set(hotel.offers.map((o) => o.row_id));
  }, [hotel]);

  const mergeDecisions = useMemo(() => {
    if (clusterRowIds.size <= 1) return [];
    return decisions.filter(
      (d) =>
        clusterRowIds.has(d.row_a) &&
        clusterRowIds.has(d.row_b) &&
        d.final_decision === "true"
    );
  }, [decisions, clusterRowIds]);

  return (
    <div className="space-y-8 pb-10">
      {/* Top Navigation & State Toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <Link
          href="/catalogue"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-600 hover:text-teal-700 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Catalogue
        </Link>

        <div className="flex items-center gap-2 bg-slate-100 p-1 rounded-lg self-start sm:self-auto">
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
      </div>

      {/* 404 Not Found State */}
      {forceState === "empty" || notFound ? (
        <EmptyState
          title="Hotel Not Found (404)"
          description={`We could not locate a master hotel record with ID "${hotelId}". It may have been removed or never indexed.`}
          action={
            <Link href="/catalogue">
              <Button variant="outline">Browse Hotel Catalogue</Button>
            </Link>
          }
        />
      ) : forceState === "error" || error ? (
        <ErrorState
          title="Failed to Load Hotel"
          message={error || `Could not retrieve information for hotel ${hotelId}.`}
          onRetry={loadData}
        />
      ) : loading || !hotel ? (
        <div className="space-y-6">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-44 w-full" />
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : (
        <>
          {/* 1. Header: Name, Full Address, City, Pincode, Star Rating */}
          <PageHeader
            title={hotel.name}
            description={`${hotel.address ? `${hotel.address}, ` : ""}${hotel.city}${
              hotel.pincode ? ` - ${hotel.pincode}` : ""
            }`}
            badge={
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant="teal">{hotel.cluster_id}</Badge>
                {hotel.stars && (
                  <Badge variant="warning">
                    <Star className="w-3.5 h-3.5 fill-amber-400 inline mr-1" />
                    {hotel.stars} Stars
                  </Badge>
                )}
                <Badge variant="outline">
                  {hotel.offers.length} {hotel.offers.length === 1 ? "Supplier Feed" : "Merged Feeds"}
                </Badge>
              </div>
            }
          />

          {/* 2. Highlighted Best-Offer Panel */}
          {hotel.best_offer && (
            <Card className="border-teal-300 bg-gradient-to-br from-teal-50/50 via-white to-teal-50/30 shadow-sm overflow-hidden">
              <CardHeader className="py-4 px-6 border-b border-teal-100/80 bg-teal-100/30 flex flex-row items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-teal-600 text-white flex items-center justify-center shadow-xs">
                    <Tag className="w-4 h-4" />
                  </div>
                  <div>
                    <CardTitle className="text-sm font-bold text-teal-950 uppercase tracking-wider">
                      Selected Best Value Offer
                    </CardTitle>
                    <span className="text-[11px] text-teal-700 font-medium">
                      Multi-attribute utility score computed across price, terms & reliability
                    </span>
                  </div>
                </div>
                <Badge variant="teal" className="font-semibold text-xs py-1 px-3">
                  Supplier {hotel.best_offer.supplier}
                </Badge>
              </CardHeader>

              <CardContent className="p-6 space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {/* Price */}
                  <div className="p-4 rounded-xl bg-white border border-teal-100 shadow-2xs">
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1">
                      Best Price
                    </span>
                    <div className="text-2xl font-black text-teal-700">
                      ₹{Number(hotel.best_offer.price_inr).toLocaleString()}
                    </div>
                    <span className="text-[11px] text-slate-400 mt-0.5 block">per room / night</span>
                  </div>

                  {/* Supplier */}
                  <div className="p-4 rounded-xl bg-white border border-teal-100 shadow-2xs">
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1">
                      Provider
                    </span>
                    <div className="text-xl font-bold text-slate-900">
                      Supplier {hotel.best_offer.supplier}
                    </div>
                    <span className="text-[11px] text-slate-500 mt-0.5 block">
                      Reliability: <strong>{(hotel.best_offer.reliability * 100).toFixed(0)}%</strong>
                    </span>
                  </div>

                  {/* Cancellation */}
                  <div className="p-4 rounded-xl bg-white border border-teal-100 shadow-2xs">
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1">
                      Cancellation Policy
                    </span>
                    <div className="text-sm font-bold text-slate-900">
                      {hotel.best_offer.cancellation_policy}
                    </div>
                    <span className="text-[11px] text-emerald-600 font-medium mt-0.5 block">
                      Protected booking
                    </span>
                  </div>

                  {/* Payment Terms */}
                  <div className="p-4 rounded-xl bg-white border border-teal-100 shadow-2xs">
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1">
                      Payment Terms
                    </span>
                    <div className="text-sm font-bold text-slate-900">
                      {hotel.best_offer.payment_terms}
                    </div>
                    <span className="text-[11px] text-slate-400 mt-0.5 block">
                      Clear settlement
                    </span>
                  </div>
                </div>

                {/* Reason Text */}
                <div className="p-4 rounded-xl bg-white/90 border border-teal-200/80 shadow-2xs">
                  <span className="text-xs font-bold text-teal-900 uppercase tracking-wider block mb-1">
                    Value Decision Reason
                  </span>
                  <p className="text-sm text-slate-700 italic leading-relaxed">
                    &ldquo;{hotel.best_offer_reason}&rdquo;
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* 3. Offers Table (Sorted by Value Score, Best Highlighted) */}
          <Card>
            <CardHeader className="border-b border-slate-100">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Layers className="w-4 h-4 text-teal-600" /> Supplier Offers Ranking
                </CardTitle>
                <span className="text-xs text-slate-500 font-medium">
                  Ranked by composite value score (price 45%, cancellation 25%, payment 10%, reliability 20%)
                </span>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <Table className="border-0 rounded-none">
                <TableHeader>
                  <TableRow className="bg-slate-50/70 text-xs">
                    <TableHead>Rank & Supplier</TableHead>
                    <TableHead>Row ID</TableHead>
                    <TableHead>Price (INR)</TableHead>
                    <TableHead>Cancellation</TableHead>
                    <TableHead>Payment Terms</TableHead>
                    <TableHead>Reliability</TableHead>
                    <TableHead className="text-right">Value Score</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedOffers.map((offer, idx) => {
                    const isBest = offer.row_id === hotel.best_offer?.row_id;
                    return (
                      <TableRow
                        key={offer.row_id}
                        className={
                          isBest
                            ? "bg-teal-50/60 font-medium hover:bg-teal-50/90"
                            : "hover:bg-slate-50/80"
                        }
                      >
                        <TableCell className="font-semibold text-slate-900">
                          <div className="flex items-center gap-2">
                            <span className="w-5 h-5 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center text-[10px] font-bold">
                              {idx + 1}
                            </span>
                            <span>Supplier {offer.supplier}</span>
                            {isBest && (
                              <Badge variant="teal" className="text-[10px] py-0 px-1.5">
                                Best
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-xs text-slate-600">
                          {offer.row_id}
                        </TableCell>
                        <TableCell className="font-bold text-slate-900">
                          ₹{Number(offer.price_inr).toLocaleString()}
                        </TableCell>
                        <TableCell className="text-xs text-slate-700">
                          {offer.cancellation_policy}
                        </TableCell>
                        <TableCell className="text-xs text-slate-700">
                          {offer.payment_terms}
                        </TableCell>
                        <TableCell>
                          <Badge variant="success" className="text-xs">
                            {(offer.reliability * 100).toFixed(0)}%
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-mono font-bold text-teal-700">
                          {offer.value_score.toFixed(3)}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* 4. Why these listings were merged */}
          <Card>
            <CardHeader className="border-b border-slate-100">
              <CardTitle className="text-base flex items-center gap-2">
                <GitMerge className="w-4 h-4 text-teal-600" /> Why these listings were merged
              </CardTitle>
              <p className="text-xs text-slate-500 mt-1">
                Raw supplier listings exactly as received (preserving spelling noise and missing values), alongside matching evidence.
              </p>
            </CardHeader>
            <CardContent className="space-y-6 pt-5">
              {/* Raw Supplier Feed Listings */}
              <div>
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3">
                  Raw Supplier Inventory Records ({hotel.offers.length})
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {hotel.offers.map((offer) => {
                    const raw = rawSupplierRows[offer.row_id];
                    return (
                      <div
                        key={offer.row_id}
                        className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-2 text-xs"
                      >
                        <div className="flex items-center justify-between pb-1 border-b border-slate-200/60">
                          <span className="font-bold text-slate-900">
                            Supplier {offer.supplier}
                          </span>
                          <span className="font-mono text-[11px] text-slate-500">
                            {offer.row_id}
                          </span>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-400 uppercase font-semibold block">
                            Raw Hotel Name
                          </span>
                          <span className="font-semibold text-slate-900">
                            {raw?.name || "—"}
                          </span>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-400 uppercase font-semibold block">
                            Raw Address & Locality
                          </span>
                          <span className="text-slate-600">
                            {raw?.address || <span className="text-slate-400 italic">No address provided</span>}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 pt-1 text-[11px] text-slate-500">
                          <div>
                            <strong>City:</strong> {raw?.city || "—"}
                          </div>
                          <div>
                            <strong>Pincode:</strong> {raw?.pincode || "—"}
                          </div>
                          <div>
                            <strong>Stars:</strong> {raw?.stars ? `${raw.stars}★` : "—"}
                          </div>
                          <div>
                            <strong>GPS:</strong>{" "}
                            {raw?.lat && raw?.lon ? `${Number(raw.lat).toFixed(4)}, ${Number(raw.lon).toFixed(4)}` : "—"}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Pairwise Merge Evidence */}
              <div className="pt-2">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3">
                  Pairwise Scoring & LLM Reasoning
                </h4>

                {mergeDecisions.length > 0 ? (
                  <div className="space-y-3">
                    {mergeDecisions.map((dec, idx) => (
                      <div
                        key={idx}
                        className="p-4 rounded-xl border border-slate-200 bg-white shadow-2xs space-y-2 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-bold text-slate-900 text-xs">
                            {dec.row_a} &harr; {dec.row_b}
                          </span>
                          <div className="flex items-center gap-2">
                            <Badge
                              variant={
                                dec.band === "match"
                                  ? "success"
                                  : dec.band === "unsure"
                                  ? "warning"
                                  : "default"
                              }
                            >
                              Band: {dec.band.toUpperCase()}
                            </Badge>
                            <span className="font-bold text-slate-700">
                              Score: {dec.score.toFixed(2)}
                            </span>
                          </div>
                        </div>

                        {dec.explanation && (
                          <div className="text-slate-600">
                            <strong>Rule Signals:</strong> {dec.explanation}
                          </div>
                        )}

                        {dec.llm_same && (
                          <div className="p-2.5 rounded-lg bg-teal-50 border border-teal-100 text-teal-900 space-y-1">
                            <div className="flex items-center gap-1.5 font-bold text-[11px]">
                              <CheckCircle2 className="w-3.5 h-3.5 text-teal-600" />
                              <span>LLM Judge Verdict: same = {String(dec.llm_same)}</span>
                              {dec.llm_confidence && (
                                <span className="font-normal text-teal-700">
                                  (Confidence: {(Number(dec.llm_confidence) * 100).toFixed(0)}%)
                                </span>
                              )}
                            </div>
                            {dec.llm_reason && (
                              <p className="text-[11px] italic text-teal-800 leading-relaxed">
                                &ldquo;{dec.llm_reason}&rdquo;
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 text-slate-500 text-xs leading-relaxed">
                    {hotel.offers.length === 1 ? (
                      <p>
                        This cluster consists of a single verified supplier listing (Supplier {hotel.offers[0].supplier}). No merging of separate listings was required.
                      </p>
                    ) : (
                      <p>
                        Listings merged via transitive component connectivity under the supplier uniqueness safety rule (no duplicate supplier A or C per cluster).
                      </p>
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* 5. Similar hotels kept separate */}
          <Card>
            <CardHeader className="border-b border-slate-100">
              <CardTitle className="text-base flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600" /> Similar hotels kept separate
              </CardTitle>
              <p className="text-xs text-slate-500 mt-1">
                Hotels with high name similarity (&ge; 80%) verified as distinct physical properties and prevented from false merging.
              </p>
            </CardHeader>
            <CardContent className="pt-5">
              {hotel.similar_hotels && hotel.similar_hotels.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {hotel.similar_hotels.map((sim) => (
                    <div
                      key={sim.hotel_id}
                      className="p-4 rounded-xl border border-slate-200 bg-white shadow-2xs space-y-2 text-xs hover:border-teal-300 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <span className="font-mono text-[10px] text-slate-400 font-semibold block">
                            {sim.hotel_id}
                          </span>
                          <h4 className="font-bold text-sm text-slate-900 leading-snug">
                            {sim.name}
                          </h4>
                          <span className="text-slate-500 text-[11px] mt-0.5 block">
                            Area / City: {sim.area || sim.city || "Same City"}
                          </span>
                        </div>
                        <Badge variant="warning" className="shrink-0 text-xs">
                          {(sim.similarity * 100).toFixed(0)}% Similar
                        </Badge>
                      </div>

                      <div className="p-2.5 rounded-lg bg-amber-50/60 border border-amber-200/70 text-slate-700">
                        <strong className="text-amber-900 block text-[11px] mb-0.5">
                          Reason kept apart:
                        </strong>
                        <p className="italic text-[11px] leading-relaxed">
                          {sim.reason}
                        </p>
                      </div>

                      <div className="pt-1 flex justify-end">
                        <Link
                          href={`/hotels/${sim.hotel_id}`}
                          className="font-semibold text-teal-600 hover:text-teal-700 inline-flex items-center gap-1"
                        >
                          View Hotel Profile &rarr;
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-6 text-center border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/50 text-slate-500 text-xs">
                  <CheckCircle2 className="w-5 h-5 text-emerald-500 mx-auto mb-2" />
                  <p className="font-medium text-slate-700">No deceptive look-alikes near this property.</p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    No other candidate hotel reached the 80% name similarity threshold in this city.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
