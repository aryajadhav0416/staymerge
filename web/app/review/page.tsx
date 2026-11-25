"use client";

import React, { useEffect, useState, useMemo, useCallback } from "react";
import {
  PageHeader,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Badge,
  Button,
  Skeleton,
  EmptyState,
  ErrorState,
} from "@/components/ui";
import {
  getReviewQueue,
  getReviewDecisions,
  submitReview,
  getFeeds,
  Decision,
  SupplierRow,
  RecordedReview,
} from "@/lib/api";
import {
  Scale,
  CheckCircle2,
  XCircle,
  GitMerge,
  Split,
  Building2,
  MapPin,
  Star,
  Tag,
  Phone,
  Layers,
  Sparkles,
  RotateCcw,
  AlertTriangle,
} from "lucide-react";

interface PairDecisionState {
  status: "idle" | "submitting" | "saved" | "error";
  decision?: "merge" | "split";
  error?: string;
}

export default function ReviewPage() {
  const [activeTab, setActiveTab] = useState<"pending" | "decided">("pending");
  const [queue, setQueue] = useState<Decision[]>([]);
  const [decisionsMap, setDecisionsMap] = useState<Record<string, "merge" | "split">>({});
  const [itemStates, setItemStates] = useState<Record<string, PairDecisionState>>({});
  const [supplierRows, setSupplierRows] = useState<Record<string, SupplierRow>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forceState, setForceState] = useState<"auto" | "empty" | "error">("auto");

  // Pair key generator
  const getPairKey = (rowA: string, rowB: string) => `${rowA}_${rowB}`;

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Load review queue (unsure pairs)
      // 2. Load feeds (raw listings to show side-by-side)
      // 3. Load recorded review decisions (persisted in review_decisions.csv)
      const [queueData, feedsData, savedDecisions] = await Promise.all([
        getReviewQueue(),
        getFeeds(),
        getReviewDecisions(),
      ]);

      setQueue(queueData || []);

      // Build dictionary of raw supplier rows
      const rowMap: Record<string, SupplierRow> = {};
      if (feedsData?.suppliers) {
        for (const sup of feedsData.suppliers) {
          if (sup.rows) {
            for (const r of sup.rows) {
              rowMap[r.row_id] = r;
            }
          }
        }
      }
      setSupplierRows(rowMap);

      // Map saved decisions
      const dMap: Record<string, "merge" | "split"> = {};
      const sMap: Record<string, PairDecisionState> = {};

      if (savedDecisions && savedDecisions.length > 0) {
        for (const rec of savedDecisions) {
          const key1 = getPairKey(rec.row_a, rec.row_b);
          const key2 = getPairKey(rec.row_b, rec.row_a);
          dMap[key1] = rec.action;
          dMap[key2] = rec.action;
          sMap[key1] = { status: "saved", decision: rec.action };
          sMap[key2] = { status: "saved", decision: rec.action };
        }
      }

      // Check localStorage for offline/client fallback decisions
      if (typeof window !== "undefined") {
        try {
          const stored = localStorage.getItem("staymerge_review_decisions");
          if (stored) {
            const parsed = JSON.parse(stored) as Record<string, "merge" | "split">;
            for (const [k, v] of Object.entries(parsed)) {
              if (!dMap[k]) {
                dMap[k] = v;
                sMap[k] = { status: "saved", decision: v };
              }
            }
          }
        } catch {
          // ignore localStorage parsing errors
        }
      }

      setDecisionsMap(dMap);
      setItemStates(sMap);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load review queue");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle human review decision submission
  const handleDecision = async (
    pair: Decision,
    action: "merge" | "split"
  ) => {
    const pairKey = getPairKey(pair.row_a, pair.row_b);
    const previousDecision = decisionsMap[pairKey];

    // Optimistic UI update: immediately mark state as saved with chosen action
    setItemStates((prev) => ({
      ...prev,
      [pairKey]: { status: "submitting", decision: action },
    }));
    setDecisionsMap((prev) => ({
      ...prev,
      [pairKey]: action,
      [getPairKey(pair.row_b, pair.row_a)]: action,
    }));

    try {
      await submitReview({
        pair_id: pairKey,
        row_a: pair.row_a,
        row_b: pair.row_b,
        action,
        notes: `Reviewed via StayMerge web UI`,
      });

      // Update state to saved
      setItemStates((prev) => ({
        ...prev,
        [pairKey]: { status: "saved", decision: action },
      }));

      // Persist in localStorage so it is guaranteed to show after refresh
      if (typeof window !== "undefined") {
        try {
          const stored = localStorage.getItem("staymerge_review_decisions");
          const existing = stored ? JSON.parse(stored) : {};
          existing[pairKey] = action;
          existing[getPairKey(pair.row_b, pair.row_a)] = action;
          localStorage.setItem("staymerge_review_decisions", JSON.stringify(existing));
        } catch {
          // ignore
        }
      }
    } catch (err: unknown) {
      // Revert optimistic update on failure and display retryable error
      const errorMessage = err instanceof Error ? err.message : "Failed to save review decision";
      setItemStates((prev) => ({
        ...prev,
        [pairKey]: {
          status: "error",
          decision: previousDecision,
          error: errorMessage,
        },
      }));
      setDecisionsMap((prev) => {
        const next = { ...prev };
        if (previousDecision) {
          next[pairKey] = previousDecision;
        } else {
          delete next[pairKey];
          delete next[getPairKey(pair.row_b, pair.row_a)];
        }
        return next;
      });
    }
  };

  // Group queue pairs into Pending and Decided
  const { pendingPairs, decidedPairs } = useMemo(() => {
    const pending: Decision[] = [];
    const decided: Decision[] = [];

    for (const pair of queue) {
      const key = getPairKey(pair.row_a, pair.row_b);
      if (decisionsMap[key]) {
        decided.push(pair);
      } else {
        pending.push(pair);
      }
    }

    return { pendingPairs: pending, decidedPairs: decided };
  }, [queue, decisionsMap]);

  const activePairs = activeTab === "pending" ? pendingPairs : decidedPairs;

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <PageHeader
        title="Review Queue"
        description="Inspect borderline unsure pairs with conflicting signals side-by-side, verify LLM recommendations, and approve or reject merges."
        badge={
          <Badge variant="teal">
            {pendingPairs.length} Pending
          </Badge>
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

      {/* Tabs */}
      <div className="flex items-center justify-between border-b border-slate-200">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setActiveTab("pending")}
            className={`pb-3 px-1 text-sm font-semibold border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "pending"
                ? "border-teal-600 text-teal-800"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <span>Pending Review</span>
            <Badge
              variant={pendingPairs.length > 0 ? "teal" : "default"}
              className="text-xs"
            >
              {pendingPairs.length}
            </Badge>
          </button>

          <button
            onClick={() => setActiveTab("decided")}
            className={`pb-3 px-1 text-sm font-semibold border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "decided"
                ? "border-teal-600 text-teal-800"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <span>Decided</span>
            <Badge variant="default" className="text-xs">
              {decidedPairs.length}
            </Badge>
          </button>
        </div>

        <div className="text-xs text-slate-500 pb-2 hidden sm:block">
          Total Unsure Pairs: <span className="font-semibold text-slate-700">{queue.length}</span>
        </div>
      </div>

      {/* Content States */}
      {forceState === "error" || (forceState === "auto" && error) ? (
        <ErrorState
          title="Failed to Load Review Queue"
          message={error || "An error occurred while fetching candidate pairs from the matching engine."}
          onRetry={loadData}
        />
      ) : forceState === "empty" || (forceState === "auto" && !loading && activePairs.length === 0) ? (
        <EmptyState
          title={activeTab === "pending" ? "No Pending Pairs to Review" : "No Decided Pairs Yet"}
          description={
            activeTab === "pending"
              ? "All borderline pairs have been reviewed or none required human-in-the-loop inspection."
              : "Approve or reject pairs in the Pending tab to see them listed here."
          }
          action={
            activeTab === "decided" ? (
              <Button variant="outline" onClick={() => setActiveTab("pending")}>
                Go to Pending Queue
              </Button>
            ) : undefined
          }
        />
      ) : loading && forceState === "auto" ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-64 w-full rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {activePairs.map((pair) => {
            const pairKey = getPairKey(pair.row_a, pair.row_b);
            const state = itemStates[pairKey];
            const currentDecision = decisionsMap[pairKey];
            const rowA = supplierRows[pair.row_a];
            const rowB = supplierRows[pair.row_b];

            // Compute field differences for highlight
            const nameDiff =
              rowA?.name && rowB?.name
                ? rowA.name.trim().toLowerCase() !== rowB.name.trim().toLowerCase()
                : false;
            const addressDiff =
              rowA?.address && rowB?.address
                ? rowA.address.trim().toLowerCase() !== rowB.address.trim().toLowerCase()
                : false;
            const cityDiff =
              rowA?.city && rowB?.city
                ? rowA.city.trim().toLowerCase() !== rowB.city.trim().toLowerCase()
                : false;
            const pincodeDiff =
              rowA?.pincode && rowB?.pincode
                ? rowA.pincode.trim() !== rowB.pincode.trim()
                : false;
            const phoneDiff =
              rowA?.phone && rowB?.phone
                ? rowA.phone.trim() !== rowB.phone.trim()
                : false;
            const starsDiff =
              rowA?.stars !== undefined && rowB?.stars !== undefined && rowA?.stars !== null && rowB?.stars !== null
                ? String(rowA.stars).trim() !== String(rowB.stars).trim()
                : false;

            return (
              <Card
                key={pairKey}
                className={`overflow-hidden transition-all border ${
                  currentDecision === "merge"
                    ? "border-teal-300 ring-1 ring-teal-200 bg-teal-50/10"
                    : currentDecision === "split"
                    ? "border-amber-300 ring-1 ring-amber-200 bg-amber-50/10"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                {/* Pair Header Banner */}
                <CardHeader className="bg-slate-50/70 border-b border-slate-100 py-3 px-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-bold text-slate-800 bg-white border border-slate-200 px-2 py-0.5 rounded shadow-2xs">
                      {pair.row_a}
                    </span>
                    <span className="text-xs text-slate-400 font-bold">&harr;</span>
                    <span className="font-mono text-xs font-bold text-slate-800 bg-white border border-slate-200 px-2 py-0.5 rounded shadow-2xs">
                      {pair.row_b}
                    </span>
                    <Badge variant="warning" className="capitalize">
                      Band: {pair.band || "unsure"}
                    </Badge>
                    <Badge variant="default">
                      Rule Score: {typeof pair.score === "number" ? pair.score.toFixed(2) : pair.score}
                    </Badge>
                  </div>

                  {/* Decision Status Badge */}
                  {currentDecision && (
                    <div className="flex items-center gap-1.5 self-start sm:self-auto">
                      <span className="text-xs text-slate-500 font-medium">Saved Decision:</span>
                      <Badge
                        variant={currentDecision === "merge" ? "teal" : "warning"}
                        className="font-bold inline-flex items-center gap-1"
                      >
                        {currentDecision === "merge" ? (
                          <>
                            <CheckCircle2 className="w-3.5 h-3.5 inline" />
                            <span>Approved Merge</span>
                          </>
                        ) : (
                          <>
                            <XCircle className="w-3.5 h-3.5 inline" />
                            <span>Kept Separate (Split)</span>
                          </>
                        )}
                      </Badge>
                    </div>
                  )}
                </CardHeader>

                <CardContent className="p-5 space-y-5">
                  {/* Side-by-side Supplier Listings */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Listing A */}
                    <div className="p-4 rounded-xl border border-slate-200 bg-white shadow-2xs space-y-3">
                      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                        <div className="flex items-center gap-2">
                          <Badge variant="teal">Supplier {rowA?.supplier || pair.row_a[0]}</Badge>
                          <span className="font-mono text-xs text-slate-500 font-semibold">{pair.row_a}</span>
                        </div>
                        {pair.hotel_a_id && (
                          <span className="text-[11px] font-mono text-slate-400">Cluster {pair.hotel_a_id}</span>
                        )}
                      </div>

                      <div className="space-y-2 text-xs">
                        {/* Name */}
                        <div>
                          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Hotel Name</div>
                          <div
                            className={`font-semibold text-sm ${
                              nameDiff ? "bg-amber-100/70 text-amber-950 px-1.5 py-0.5 rounded -mx-1" : "text-slate-900"
                            }`}
                          >
                            {rowA?.name || <span className="text-slate-400 italic">No name provided</span>}
                          </div>
                        </div>

                        {/* Address */}
                        <div>
                          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Address</div>
                          <div
                            className={`text-slate-700 leading-relaxed ${
                              addressDiff ? "bg-amber-100/70 text-amber-950 px-1.5 py-0.5 rounded -mx-1" : ""
                            }`}
                          >
                            {rowA?.address || <span className="text-slate-400 italic">No address provided</span>}
                          </div>
                        </div>

                        {/* Metadata Pills */}
                        <div className="grid grid-cols-2 gap-2 pt-1">
                          <div>
                            <span className="text-slate-400 text-[10px] block">City:</span>
                            <span
                              className={`font-medium ${
                                cityDiff ? "bg-amber-100/70 text-amber-950 px-1 rounded" : "text-slate-700"
                              }`}
                            >
                              {rowA?.city || "-"}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 text-[10px] block">Pincode:</span>
                            <span
                              className={`font-mono font-medium ${
                                pincodeDiff ? "bg-amber-100/70 text-amber-950 px-1 rounded" : "text-slate-700"
                              }`}
                            >
                              {rowA?.pincode || "-"}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 text-[10px] block">Phone:</span>
                            <span
                              className={`font-mono font-medium ${
                                phoneDiff ? "bg-amber-100/70 text-amber-950 px-1 rounded" : "text-slate-700"
                              }`}
                            >
                              {rowA?.phone || "-"}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 text-[10px] block">Star Rating:</span>
                            <span
                              className={`font-medium ${
                                starsDiff ? "bg-amber-100/70 text-amber-950 px-1 rounded" : "text-slate-700"
                              }`}
                            >
                              {rowA?.stars ? `${rowA.stars} ★` : "-"}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Listing B */}
                    <div className="p-4 rounded-xl border border-slate-200 bg-white shadow-2xs space-y-3">
                      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                        <div className="flex items-center gap-2">
                          <Badge variant="teal">Supplier {rowB?.supplier || pair.row_b[0]}</Badge>
                          <span className="font-mono text-xs text-slate-500 font-semibold">{pair.row_b}</span>
                        </div>
                        {pair.hotel_b_id && (
                          <span className="text-[11px] font-mono text-slate-400">Cluster {pair.hotel_b_id}</span>
                        )}
                      </div>

                      <div className="space-y-2 text-xs">
                        {/* Name */}
                        <div>
                          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Hotel Name</div>
                          <div
                            className={`font-semibold text-sm ${
                              nameDiff ? "bg-amber-100/70 text-amber-950 px-1.5 py-0.5 rounded -mx-1" : "text-slate-900"
                            }`}
                          >
                            {rowB?.name || <span className="text-slate-400 italic">No name provided</span>}
                          </div>
                        </div>

                        {/* Address */}
                        <div>
                          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Address</div>
                          <div
                            className={`text-slate-700 leading-relaxed ${
                              addressDiff ? "bg-amber-100/70 text-amber-950 px-1.5 py-0.5 rounded -mx-1" : ""
                            }`}
                          >
                            {rowB?.address || <span className="text-slate-400 italic">No address provided</span>}
                          </div>
                        </div>

                        {/* Metadata Pills */}
                        <div className="grid grid-cols-2 gap-2 pt-1">
                          <div>
                            <span className="text-slate-400 text-[10px] block">City:</span>
                            <span
                              className={`font-medium ${
                                cityDiff ? "bg-amber-100/70 text-amber-950 px-1 rounded" : "text-slate-700"
                              }`}
                            >
                              {rowB?.city || "-"}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 text-[10px] block">Pincode:</span>
                            <span
                              className={`font-mono font-medium ${
                                pincodeDiff ? "bg-amber-100/70 text-amber-950 px-1 rounded" : "text-slate-700"
                              }`}
                            >
                              {rowB?.pincode || "-"}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 text-[10px] block">Phone:</span>
                            <span
                              className={`font-mono font-medium ${
                                phoneDiff ? "bg-amber-100/70 text-amber-950 px-1 rounded" : "text-slate-700"
                              }`}
                            >
                              {rowB?.phone || "-"}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 text-[10px] block">Star Rating:</span>
                            <span
                              className={`font-medium ${
                                starsDiff ? "bg-amber-100/70 text-amber-950 px-1 rounded" : "text-slate-700"
                              }`}
                            >
                              {rowB?.stars ? `${rowB.stars} ★` : "-"}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Rule Score Explanation & LLM Judge Reasoning */}
                  <div className="p-4 rounded-xl border border-slate-200/90 bg-slate-50/70 space-y-3">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Scale className="w-4 h-4 text-teal-600" />
                        <span className="text-xs font-bold text-slate-800">Rule Signals & Features:</span>
                        <span className="text-xs text-slate-600">{pair.explanation || "City match"}</span>
                      </div>

                      {pair.llm_same !== null && pair.llm_same !== undefined && (
                        <div className="flex items-center gap-2 text-xs">
                          <Sparkles className="w-3.5 h-3.5 text-teal-600" />
                          <span className="font-semibold text-slate-700">LLM Verdict:</span>
                          <Badge
                            variant={String(pair.llm_same).toLowerCase() === "true" ? "teal" : "warning"}
                            className="font-bold text-[11px]"
                          >
                            {String(pair.llm_same).toLowerCase() === "true" ? "Match (Same)" : "Different (Separate)"}
                          </Badge>
                          {pair.llm_confidence && (
                            <span className="text-slate-500 text-[11px]">
                              ({Math.round(Number(pair.llm_confidence) * 100)}% conf)
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {pair.llm_reason && (
                      <div className="p-3 rounded-lg bg-white border border-slate-200 text-xs text-slate-700 leading-relaxed">
                        <span className="font-bold text-teal-900 block mb-0.5">LLM Reasoning:</span>
                        {pair.llm_reason}
                      </div>
                    )}
                  </div>

                  {/* Action Bar / Error State with Retry */}
                  {state?.status === "error" && (
                    <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg flex items-center justify-between gap-3 text-xs text-rose-800">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                        <span>Failed to save decision: {state.error}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDecision(pair, "merge")}
                          className="h-7 text-xs border-rose-300 text-rose-800 hover:bg-rose-100"
                        >
                          Retry Merge
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDecision(pair, "split")}
                          className="h-7 text-xs border-rose-300 text-rose-800 hover:bg-rose-100"
                        >
                          Retry Split
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Approve / Reject Controls */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-slate-100">
                    <span className="text-xs text-slate-500">
                      Human Reviewer Action:{" "}
                      <span className="text-slate-700 font-medium">
                        {currentDecision
                          ? `Currently set to ${currentDecision === "merge" ? "Approved Merge" : "Rejected (Split)"}`
                          : "Pending approval"}
                      </span>
                    </span>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant={currentDecision === "merge" ? "primary" : "outline"}
                        disabled={state?.status === "submitting"}
                        onClick={() => handleDecision(pair, "merge")}
                        className={`gap-1.5 ${
                          currentDecision === "merge"
                            ? "bg-teal-600 hover:bg-teal-700 text-white"
                            : "hover:border-teal-400 hover:text-teal-700"
                        }`}
                      >
                        <GitMerge className="w-3.5 h-3.5" />
                        <span>{currentDecision === "merge" ? "Approved Merge" : "Approve Merge"}</span>
                      </Button>

                      <Button
                        size="sm"
                        variant={currentDecision === "split" ? "danger" : "outline"}
                        disabled={state?.status === "submitting"}
                        onClick={() => handleDecision(pair, "split")}
                        className={`gap-1.5 ${
                          currentDecision === "split"
                            ? "bg-amber-600 hover:bg-amber-700 text-white border-amber-600"
                            : "hover:border-amber-400 hover:text-amber-700"
                        }`}
                      >
                        <Split className="w-3.5 h-3.5" />
                        <span>{currentDecision === "split" ? "Kept Separate" : "Reject"}</span>
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
