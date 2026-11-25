import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import HotelDetailPage from "@/app/hotels/[id]/page";
import * as api from "@/lib/api";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "C9999" }),
}));

describe("HotelDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the not-found state without crashing when hotel does not exist (404)", async () => {
    vi.spyOn(api, "getHotelDetail").mockRejectedValue(new Error("Hotel not found (404)"));
    vi.spyOn(api, "getDecisions").mockResolvedValue([]);
    vi.spyOn(api, "getFeeds").mockResolvedValue({
      suppliers: [],
    });

    render(<HotelDetailPage />);

    await waitFor(() => {
      expect(screen.getByText(/Hotel Not Found/i)).toBeInTheDocument();
    });

    // Verify the action button "Browse Hotel Catalogue" renders without ReferenceError
    const browseBtn = screen.getByRole("button", { name: /Browse Hotel Catalogue/i });
    expect(browseBtn).toBeInTheDocument();
  });

  it("renders the error state when an unexpected error occurs", async () => {
    vi.spyOn(api, "getHotelDetail").mockRejectedValue(new Error("503 Service Unavailable"));
    vi.spyOn(api, "getDecisions").mockResolvedValue([]);
    vi.spyOn(api, "getFeeds").mockResolvedValue({
      suppliers: [],
    });

    render(<HotelDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Failed to Load Hotel")).toBeInTheDocument();
      expect(screen.getByText("503 Service Unavailable")).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole("button", { name: /retry/i });
    expect(retryBtn).toBeInTheDocument();
  });
});
