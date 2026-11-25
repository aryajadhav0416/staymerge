/**
 * Typed API Client for StayMerge FastAPI Backend.
 * Base URL configured via NEXT_PUBLIC_API_URL (default: http://localhost:8000).
 * Mock mode supported via NEXT_PUBLIC_USE_MOCK=1.
 */

import mockHotels from "../mock/hotels.json";
import mockHotelDetail from "../mock/hotel_detail.json";
import mockDecisions from "../mock/decisions.json";
import mockMetrics from "../mock/metrics.json";
import mockFeeds from "../mock/feeds.json";

// ---------------------------------------------------------------------------
// Type Definitions (matching P7b backend contract exactly)
// ---------------------------------------------------------------------------

export interface Offer {
  row_id: string;
  supplier: string;
  price_inr: number;
  cancellation_policy: string;
  payment_terms: string;
  reliability: number;
}

export interface SimilarHotel {
  hotel_id: string;
  name: string;
  similarity: number;
  reason: string;
  area?: string | null;
  city?: string | null;
}

export interface HotelSummary {
  cluster_id: string;
  name: string;
  address: string;
  pincode: string;
  city: string;
  lat: number | null;
  lon: number | null;
  stars: string | null;
  offers: Offer[];
  best_offer: Offer;
  best_offer_reason: string;
}

export interface HotelDetail extends HotelSummary {
  similar_hotels: SimilarHotel[];
}

export interface Decision {
  row_a: string;
  row_b: string;
  hotel_a_id?: string | null;
  hotel_b_id?: string | null;
  score: number;
  band: string;
  llm_same?: string | null;
  llm_confidence?: string | null;
  llm_reason: string;
  final_decision: string;
  explanation: string;
}

export interface Metrics {
  precision: number;
  recall: number;
  f1: number;
  hard_row_recall: number;
  trap_false_merges: number;
  total_trap_pairs: number;
  predicted_hotels: number;
  true_hotels: number;
  rows_scored: number;
}

export interface SupplierRow {
  row_id: string;
  supplier: string;
  supplier_hotel_id?: string | null;
  name?: string | null;
  address?: string | null;
  city?: string | null;
  pincode?: string | null;
  lat?: number | null;
  lon?: number | null;
  phone?: string | null;
  stars?: number | string | null;
  price_inr?: number | null;
  cancellation_policy?: string | null;
  payment_terms?: string | null;
}

export interface SupplierFeed {
  supplier: string;
  name: string;
  row_count: number;
  reliability: number;
  rows?: SupplierRow[];
}

export interface FeedsResponse {
  suppliers: SupplierFeed[];
}

export interface ReviewDecisionRequest {
  pair_id?: string;
  row_a: string;
  row_b: string;
  action: "merge" | "split";
  notes?: string;
}

export interface ReviewDecisionResponse {
  status: string;
  message: string;
  recorded: ReviewDecisionRequest;
}

// ---------------------------------------------------------------------------
// Configuration & Client
// ---------------------------------------------------------------------------

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function isMockEnabled(): boolean {
  return process.env.NEXT_PUBLIC_USE_MOCK === "1";
}

async function fetchFromApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers || {}),
      },
    });

    if (!res.ok) {
      let errorMsg = `API request failed with status ${res.status}`;
      try {
        const errorData = await res.json();
        if (errorData?.detail) {
          errorMsg = errorData.detail;
        }
      } catch {
        // ignore json parse error
      }
      throw new Error(errorMsg);
    }

    return (await res.json()) as T;
  } catch (err: unknown) {
    if (err instanceof Error) {
      throw err;
    }
    throw new Error(`Network error calling ${endpoint}`);
  }
}

// ---------------------------------------------------------------------------
// API Endpoint Functions
// ---------------------------------------------------------------------------

/**
 * Health check endpoint.
 */
export async function getHealth(): Promise<{ status: string; mock_mode: boolean }> {
  if (isMockEnabled()) {
    return { status: "ok", mock_mode: true };
  }
  return fetchFromApi<{ status: string; mock_mode: boolean }>("/health");
}

/**
 * Get list of master hotels in the catalogue.
 */
export async function getHotels(params?: { city?: string; q?: string }): Promise<HotelSummary[]> {
  if (isMockEnabled()) {
    let hotels = mockHotels as HotelSummary[];
    if (params?.city) {
      hotels = hotels.filter(
        (h) => h.city.toLowerCase() === params.city!.toLowerCase()
      );
    }
    if (params?.q) {
      const qLower = params.q.toLowerCase();
      hotels = hotels.filter(
        (h) =>
          h.name.toLowerCase().includes(qLower) ||
          h.address.toLowerCase().includes(qLower)
      );
    }
    return hotels;
  }

  const query = new URLSearchParams();
  if (params?.city) query.set("city", params.city);
  if (params?.q) query.set("q", params.q);
  const qs = query.toString();

  return fetchFromApi<HotelSummary[]>(`/hotels${qs ? `?${qs}` : ""}`);
}

/**
 * Alias for getHotels matching GET /catalogue.
 */
export async function getCatalogue(params?: { city?: string; q?: string }): Promise<HotelSummary[]> {
  return getHotels(params);
}

/**
 * Get details for a specific hotel including look-alike similar hotels kept separate.
 */
export async function getHotelDetail(hotelId: string): Promise<HotelDetail> {
  if (isMockEnabled()) {
    const detail = { ...(mockHotelDetail as HotelDetail) };
    if (detail.cluster_id === hotelId || hotelId === "C0001") {
      detail.cluster_id = hotelId;
      return detail;
    }
    throw new Error(`Hotel ${hotelId} not found`);
  }

  return fetchFromApi<HotelDetail>(`/hotels/${encodeURIComponent(hotelId)}`);
}

/**
 * Get candidate pair decisions with scoring explanations.
 */
export async function getDecisions(params?: {
  band?: string;
  final_decision?: string;
}): Promise<Decision[]> {
  if (isMockEnabled()) {
    let decisions = mockDecisions as Decision[];
    if (params?.band) {
      decisions = decisions.filter((d) => d.band === params.band);
    }
    if (params?.final_decision) {
      decisions = decisions.filter(
        (d) => d.final_decision === params.final_decision
      );
    }
    return decisions;
  }

  const query = new URLSearchParams();
  if (params?.band) query.set("band", params.band);
  if (params?.final_decision) query.set("final_decision", params.final_decision);
  const qs = query.toString();

  return fetchFromApi<Decision[]>(`/decisions${qs ? `?${qs}` : ""}`);
}

/**
 * Get matcher accuracy metrics against ground truth.
 */
export async function getMetrics(): Promise<Metrics> {
  if (isMockEnabled()) {
    return mockMetrics as Metrics;
  }
  return fetchFromApi<Metrics>("/metrics");
}

/**
 * Get raw supplier feeds metadata and counts.
 */
export async function getFeeds(): Promise<FeedsResponse> {
  if (isMockEnabled()) {
    return mockFeeds as FeedsResponse;
  }
  return fetchFromApi<FeedsResponse>("/feeds");
}

/**
 * Submit human-in-the-loop review decision for a pair.
 */
export async function submitReview(
  req: ReviewDecisionRequest
): Promise<ReviewDecisionResponse> {
  if (isMockEnabled()) {
    return {
      status: "success",
      message: `Mock review decision recorded: ${req.action} pair (${req.row_a}, ${req.row_b})`,
      recorded: req,
    };
  }

  return fetchFromApi<ReviewDecisionResponse>("/review-decision", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

/**
 * Get the review queue of pairs needing or eligible for human review.
 */
export async function getReviewQueue(): Promise<Decision[]> {
  if (isMockEnabled()) {
    return mockDecisions as Decision[];
  }
  return fetchFromApi<Decision[]>("/review-queue");
}

/**
 * Get previously recorded human review decisions.
 */
export interface RecordedReview {
  pair_id: string;
  row_a: string;
  row_b: string;
  action: "merge" | "split";
  notes?: string;
}

export async function getReviewDecisions(): Promise<RecordedReview[]> {
  if (isMockEnabled()) {
    return [];
  }
  try {
    return await fetchFromApi<RecordedReview[]>("/review-decisions");
  } catch {
    return [];
  }
}

