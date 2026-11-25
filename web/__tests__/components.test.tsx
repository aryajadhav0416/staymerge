import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";

describe("Button component", () => {
  it("renders with children", () => {
    render(<Button>Click Me</Button>);
    expect(screen.getByRole("button", { name: /click me/i })).toBeInTheDocument();
  });

  it("handles click events", () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Submit</Button>);
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("is disabled when isLoading is true", () => {
    render(<Button isLoading>Loading...</Button>);
    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
  });
});

describe("ErrorState component", () => {
  it("renders error title and message", () => {
    render(
      <ErrorState
        title="Failed to Load"
        message="Backend service is unreachable."
      />
    );
    expect(screen.getByText("Failed to Load")).toBeInTheDocument();
    expect(screen.getByText("Backend service is unreachable.")).toBeInTheDocument();
  });

  it("renders retry button and fires onRetry", () => {
    const handleRetry = vi.fn();
    render(<ErrorState onRetry={handleRetry} />);
    const retryBtn = screen.getByRole("button", { name: /retry/i });
    expect(retryBtn).toBeInTheDocument();
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });
});

