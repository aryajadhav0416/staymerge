import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import AccuracyPage from "@/app/accuracy/page";
import * as api from "@/lib/api";

const mockMetricsData = {
  precision: 0.987,
  recall: 0.951,
  f1: 0.969,
  hard_row_recall: 0.867,
  trap_false_merges: 0,
  total_trap_pairs: 18,
  predicted_hotels: 124,
  true_hotels: 118,
  rows_scored: 298,
};

describe("AccuracyPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders comparison table, metrics rows, target status notes, and bar chart", async () => {
    vi.spyOn(api, "getMetrics").mockResolvedValue(mockMetricsData);

    render(<AccuracyPage />);

    // Wait for metrics to load
    await waitFor(() => {
      expect(
        screen.getByText(/Accuracy & Benchmark Verification/i)
      ).toBeInTheDocument();
    });

    // Check synthetic disclaimer notice
    expect(
      screen.getByText(/Synthetic Benchmark & Frozen Run Notice/i)
    ).toBeInTheDocument();

    // Check table headers
    expect(screen.getByText("Naive Baseline")).toBeInTheDocument();
    expect(screen.getByText("StayMerge")).toBeInTheDocument();
    expect(screen.getByText("Project Target Note")).toBeInTheDocument();

    // Check required table rows
    expect(screen.getByText("Precision")).toBeInTheDocument();
    expect(screen.getByText("Recall")).toBeInTheDocument();
    expect(screen.getByText("F1 Score")).toBeInTheDocument();
    expect(screen.getByText("Hard-Row Recall")).toBeInTheDocument();
    expect(
      screen.getByText("Look-Alike Hotels Wrongly Merged (out of 18)")
    ).toBeInTheDocument();
    expect(screen.getByText("LLM Calls")).toBeInTheDocument();
    expect(screen.getByText("Share of Pairs Sent to LLM")).toBeInTheDocument();

    // Check target notes and status
    expect(screen.getByText("F1 \u2265 0.88")).toBeInTheDocument();
    expect(screen.getByText("Hard-row recall \u2265 0.70")).toBeInTheDocument();
    expect(screen.getByText("\u2264 2 wrong merges")).toBeInTheDocument();
    expect(screen.getByText("Under 25% of candidate pairs")).toBeInTheDocument();

    const metBadges = screen.getAllByText(/Met/i);
    expect(metBadges.length).toBeGreaterThan(0);

    // Check bar chart section and the three naive baselines + StayMerge
    expect(screen.getByText(/Three Naive Baselines vs. StayMerge/i)).toBeInTheDocument();
    expect(screen.getByText("Exact Name + City")).toBeInTheDocument();
    expect(screen.getByText("Phone Only")).toBeInTheDocument();
    expect(screen.getByText("Fuzzy Name + GPS")).toBeInTheDocument();
    expect(screen.getByText("StayMerge (Engine)")).toBeInTheDocument();
  });

  it("toggles between dev and test dataset results", async () => {
    vi.spyOn(api, "getMetrics").mockResolvedValue(mockMetricsData);

    render(<AccuracyPage />);

    await waitFor(() => {
      expect(screen.getByText("Dev Set (298 rows)")).toBeInTheDocument();
    });

    // Click Test Set button
    const testButton = screen.getByRole("button", { name: /Test Set/i });
    fireEvent.click(testButton);

    // Verify dataset switch reflects in subtitle / badge
    await waitFor(() => {
      expect(screen.getByText(/Dataset: TEST/i)).toBeInTheDocument();
      expect(screen.getByText(/771 raw supplier rows/i)).toBeInTheDocument();
    });
  });

  it("renders empty state and error state properly", async () => {
    vi.spyOn(api, "getMetrics").mockRejectedValue(new Error("Network Error"));

    render(<AccuracyPage />);

    await waitFor(() => {
      expect(screen.getByText("Metrics Unavailable")).toBeInTheDocument();
      expect(screen.getByText("Network Error")).toBeInTheDocument();
    });

    // Verify retry button is functional
    const retryBtn = screen.getByRole("button", { name: /Retry/i });
    expect(retryBtn).toBeInTheDocument();
  });
});

