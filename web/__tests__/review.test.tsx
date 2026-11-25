import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ReviewPage from "@/app/review/page";
import * as api from "@/lib/api";

const mockQueue: api.Decision[] = [
  {
    row_a: "A-0001",
    row_b: "B-0084",
    hotel_a_id: "C0001",
    hotel_b_id: "C0001",
    score: 2.38,
    band: "unsure",
    llm_same: "True",
    llm_confidence: "0.95",
    llm_reason: "Same entity, both in Hinjewadi, Pune.",
    final_decision: "true",
    explanation: "name 0.73, same stars",
  },
  {
    row_a: "A-0006",
    row_b: "C-0083",
    hotel_a_id: "C0006",
    hotel_b_id: "C0083",
    score: 2.6,
    band: "unsure",
    llm_same: "False",
    llm_confidence: "0.95",
    llm_reason: "Different addresses and phones.",
    final_decision: "false",
    explanation: "name 0.67, phone differs",
  },
];

const mockFeeds: api.FeedsResponse = {
  suppliers: [
    {
      supplier: "A",
      name: "Supplier A",
      row_count: 2,
      reliability: 0.95,
      rows: [
        {
          row_id: "A-0001",
          supplier: "A",
          name: "Srhee Krishna Inn",
          address: "Hinjewadi Phase 1",
          city: "Pune",
          pincode: "411057",
          stars: 2,
          phone: "9876543210",
        },
        {
          row_id: "A-0006",
          supplier: "A",
          name: "Grand Palace Hotel",
          address: "Ring Road",
          city: "Bangalore",
          pincode: "560001",
          stars: 4,
          phone: "9123456789",
        },
      ],
    },
    {
      supplier: "B",
      name: "Supplier B",
      row_count: 1,
      reliability: 0.88,
      rows: [
        {
          row_id: "B-0084",
          supplier: "B",
          name: "Shree Krishna Inn",
          address: "Hinjawadi",
          city: "Pune",
          pincode: "411057",
          stars: 2,
          phone: "9876543210",
        },
      ],
    },
    {
      supplier: "C",
      name: "Supplier C",
      row_count: 1,
      reliability: 0.92,
      rows: [
        {
          row_id: "C-0083",
          supplier: "C",
          name: "The Grand Residency",
          address: "Residency Road",
          city: "Bangalore",
          pincode: "560001",
          stars: 4,
          phone: "9123456780",
        },
      ],
    },
  ],
};

describe("ReviewPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.spyOn(api, "getReviewQueue").mockResolvedValue(mockQueue);
    vi.spyOn(api, "getFeeds").mockResolvedValue(mockFeeds);
    vi.spyOn(api, "getReviewDecisions").mockResolvedValue([]);
  });

  it("renders pending review queue pairs side-by-side with rule score and LLM reasons", async () => {
    render(<ReviewPage />);

    await waitFor(() => {
      expect(screen.getByText("Srhee Krishna Inn")).toBeInTheDocument();
      expect(screen.getByText("Shree Krishna Inn")).toBeInTheDocument();
    });

    // Check LLM reason and rule scores
    expect(screen.getByText(/Same entity, both in Hinjewadi, Pune/i)).toBeInTheDocument();
    expect(screen.getByText(/Rule Score: 2.38/i)).toBeInTheDocument();

    // Check pending count badge
    expect(screen.getByText("2 Pending")).toBeInTheDocument();
  });

  it("handles approve merge immediately and records decision", async () => {
    const submitSpy = vi.spyOn(api, "submitReview").mockResolvedValue({
      status: "success",
      message: "Approved merge",
      recorded: { row_a: "A-0001", row_b: "B-0084", action: "merge" },
    });

    render(<ReviewPage />);

    await waitFor(() => {
      expect(screen.getByText("Srhee Krishna Inn")).toBeInTheDocument();
    });

    const approveButtons = screen.getAllByRole("button", { name: /Approve Merge/i });
    fireEvent.click(approveButtons[0]);

    // Check that submit API was called with the right payload
    await waitFor(() => {
      expect(submitSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          row_a: "A-0001",
          row_b: "B-0084",
          action: "merge",
        })
      );
    });

    // Stored in localStorage
    await waitFor(() => {
      expect(localStorage.getItem("staymerge_review_decisions")).toContain('"A-0001_B-0084":"merge"');
    });

    // Switch to Decided tab to see the saved decision
    const decidedTab = screen.getByRole("button", { name: /Decided/i });
    fireEvent.click(decidedTab);

    await waitFor(() => {
      expect(screen.getAllByText("Approved Merge").length).toBeGreaterThan(0);
    });
  });

  it("handles error during review submission and shows retry option", async () => {
    vi.spyOn(api, "submitReview").mockRejectedValue(new Error("Network timeout"));

    render(<ReviewPage />);

    await waitFor(() => {
      expect(screen.getByText("Srhee Krishna Inn")).toBeInTheDocument();
    });

    const rejectButtons = screen.getAllByRole("button", { name: /Reject/i });
    fireEvent.click(rejectButtons[0]);

    // Expect error alert and Retry button to appear
    await waitFor(() => {
      expect(screen.getByText(/Failed to save decision: Network timeout/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Retry Split/i })).toBeInTheDocument();
    });
  });

  it("preserves saved decisions across tab switches and page loads", async () => {
    vi.spyOn(api, "getReviewDecisions").mockResolvedValue([
      {
        pair_id: "A-0001_B-0084",
        row_a: "A-0001",
        row_b: "B-0084",
        action: "merge",
      },
    ]);

    render(<ReviewPage />);

    // 1 pending, 1 decided
    await waitFor(() => {
      expect(screen.getByText("1 Pending")).toBeInTheDocument();
    });

    // Switch to Decided tab
    const decidedTab = screen.getByRole("button", { name: /Decided/i });
    fireEvent.click(decidedTab);

    await waitFor(() => {
      expect(screen.getAllByText("Approved Merge").length).toBeGreaterThan(0);
      expect(screen.getByText("Srhee Krishna Inn")).toBeInTheDocument();
    });
  });
});

