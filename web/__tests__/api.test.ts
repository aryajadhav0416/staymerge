import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  getHealth,
  getHotels,
  getHotelDetail,
  getDecisions,
  getMetrics,
  getFeeds,
  submitReview,
} from "@/lib/api";

describe("API Client (Mock Mode)", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK", "1");
  });

  it("getHealth returns ok and mock_mode true", async () => {
    const health = await getHealth();
    expect(health.status).toBe("ok");
    expect(health.mock_mode).toBe(true);
  });

  it("getHotels returns mock hotels list", async () => {
    const hotels = await getHotels();
    expect(Array.isArray(hotels)).toBe(true);
    expect(hotels.length).toBeGreaterThan(0);
    expect(hotels[0]).toHaveProperty("cluster_id");
    expect(hotels[0]).toHaveProperty("best_offer");
  });

  it("getHotels filters by city", async () => {
    const mumbaiHotels = await getHotels({ city: "Mumbai" });
    expect(mumbaiHotels.length).toBeGreaterThan(0);
    expect(mumbaiHotels[0].city).toBe("Mumbai");

    const none = await getHotels({ city: "NonExistentCity" });
    expect(none.length).toBe(0);
  });

  it("getHotelDetail returns hotel with similar_hotels", async () => {
    const hotel = await getHotelDetail("C0001");
    expect(hotel.cluster_id).toBe("C0001");
    expect(Array.isArray(hotel.similar_hotels)).toBe(true);
  });

  it("getDecisions returns mock decisions list", async () => {
    const decisions = await getDecisions();
    expect(Array.isArray(decisions)).toBe(true);
    expect(decisions.length).toBeGreaterThan(0);
    expect(decisions[0]).toHaveProperty("score");
  });

  it("getMetrics returns benchmark accuracy", async () => {
    const metrics = await getMetrics();
    expect(metrics.f1).toBe(0.969);
    expect(metrics.trap_false_merges).toBe(0);
  });

  it("getFeeds returns 3 suppliers", async () => {
    const feeds = await getFeeds();
    expect(feeds.suppliers.length).toBe(3);
  });

  it("submitReview returns success", async () => {
    const res = await submitReview({
      row_a: "A-0001",
      row_b: "B-0001",
      action: "merge",
    });
    expect(res.status).toBe("success");
    expect(res.recorded.action).toBe("merge");
  });
});

