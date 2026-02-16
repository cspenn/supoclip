import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import WaitlistPage from "@/app/page";

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("WaitlistPage", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("renders the hero heading", () => {
    render(<WaitlistPage />);
    expect(
      screen.getByText("The Open-Source OpusClip Alternative")
    ).toBeInTheDocument();
  });

  it("renders the waitlist form with email input and submit button", () => {
    render(<WaitlistPage />);
    expect(screen.getByText("Join the Waitlist")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Enter your email address")
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Join Waitlist" })
    ).toBeInTheDocument();
  });

  it("renders the description text", () => {
    render(<WaitlistPage />);
    expect(
      screen.getByText(
        "Be among the first to experience SupoClip when we launch."
      )
    ).toBeInTheDocument();
  });

  it("updates email input value when typing", async () => {
    const user = userEvent.setup();
    render(<WaitlistPage />);

    const input = screen.getByPlaceholderText("Enter your email address");
    await user.type(input, "test@example.com");

    expect(input).toHaveValue("test@example.com");
  });

  it("does not submit when email is empty", async () => {
    const user = userEvent.setup();
    render(<WaitlistPage />);

    const button = screen.getByRole("button", { name: "Join Waitlist" });
    await user.click(button);

    // fetch should not be called because email is empty and the form
    // has a required field + the handler guards with `if (!email) return`
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("submits form and shows success state on successful API response", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: "Successfully added to waitlist" }),
    });

    render(<WaitlistPage />);

    const input = screen.getByPlaceholderText("Enter your email address");
    await user.type(input, "test@example.com");

    const button = screen.getByRole("button", { name: "Join Waitlist" });
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText("You're On The List!")).toBeInTheDocument();
    });

    expect(
      screen.getByText(
        "Thanks for joining! We'll send you updates and early access when SupoClip is ready."
      )
    ).toBeInTheDocument();
  });

  it("sends correct payload to the API", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: "Success" }),
    });

    render(<WaitlistPage />);

    const input = screen.getByPlaceholderText("Enter your email address");
    await user.type(input, "hello@world.com");

    const button = screen.getByRole("button", { name: "Join Waitlist" });
    await user.click(button);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/waitlist", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email: "hello@world.com" }),
      });
    });
  });

  it("shows loading state while submitting", async () => {
    const user = userEvent.setup();

    // Create a promise we can control to keep the fetch pending
    let resolveFetch: (value: unknown) => void;
    const fetchPromise = new Promise((resolve) => {
      resolveFetch = resolve;
    });
    mockFetch.mockReturnValueOnce(fetchPromise);

    render(<WaitlistPage />);

    const input = screen.getByPlaceholderText("Enter your email address");
    await user.type(input, "test@example.com");

    const button = screen.getByRole("button", { name: "Join Waitlist" });
    await user.click(button);

    // Button should show loading text
    await waitFor(() => {
      expect(screen.getByText("Joining...")).toBeInTheDocument();
    });

    // Button should be disabled during loading
    expect(screen.getByRole("button", { name: "Joining..." })).toBeDisabled();

    // Resolve the fetch to clean up
    resolveFetch!({ ok: true, json: async () => ({}) });
  });

  it("stays on form when API returns error", async () => {
    const user = userEvent.setup();
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ error: "Server error" }),
    });

    render(<WaitlistPage />);

    const input = screen.getByPlaceholderText("Enter your email address");
    await user.type(input, "test@example.com");

    const button = screen.getByRole("button", { name: "Join Waitlist" });
    await user.click(button);

    await waitFor(() => {
      // Should NOT show success state
      expect(screen.queryByText("You're On The List!")).not.toBeInTheDocument();
    });

    // Form should still be visible
    expect(screen.getByText("Join the Waitlist")).toBeInTheDocument();
    expect(consoleSpy).toHaveBeenCalledWith("Failed to join waitlist");

    consoleSpy.mockRestore();
  });

  it("handles network errors gracefully", async () => {
    const user = userEvent.setup();
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    render(<WaitlistPage />);

    const input = screen.getByPlaceholderText("Enter your email address");
    await user.type(input, "test@example.com");

    const button = screen.getByRole("button", { name: "Join Waitlist" });
    await user.click(button);

    await waitFor(() => {
      // Should NOT show success state
      expect(screen.queryByText("You're On The List!")).not.toBeInTheDocument();
    });

    // Form should still be visible
    expect(screen.getByText("Join the Waitlist")).toBeInTheDocument();
    expect(consoleSpy).toHaveBeenCalledWith(
      "Error:",
      expect.any(Error)
    );

    consoleSpy.mockRestore();
  });

  it("clears email input after successful submission", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: "Success" }),
    });

    render(<WaitlistPage />);

    const input = screen.getByPlaceholderText("Enter your email address");
    await user.type(input, "test@example.com");
    expect(input).toHaveValue("test@example.com");

    const button = screen.getByRole("button", { name: "Join Waitlist" });
    await user.click(button);

    // After success, the form is replaced with the success message
    await waitFor(() => {
      expect(screen.getByText("You're On The List!")).toBeInTheDocument();
    });

    // The input should no longer be in the DOM (replaced by success view)
    expect(
      screen.queryByPlaceholderText("Enter your email address")
    ).not.toBeInTheDocument();
  });

  it("renders email input with type=email for browser validation", () => {
    render(<WaitlistPage />);
    const input = screen.getByPlaceholderText("Enter your email address");
    expect(input).toHaveAttribute("type", "email");
  });

  it("renders email input with required attribute", () => {
    render(<WaitlistPage />);
    const input = screen.getByPlaceholderText("Enter your email address");
    expect(input).toBeRequired();
  });

  it("renders success checkmark SVG after submission", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: "Success" }),
    });

    render(<WaitlistPage />);

    const input = screen.getByPlaceholderText("Enter your email address");
    await user.type(input, "test@example.com");

    const button = screen.getByRole("button", { name: "Join Waitlist" });
    await user.click(button);

    await waitFor(() => {
      // The SVG checkmark path should be present
      const svg = document.querySelector("svg");
      expect(svg).toBeInTheDocument();
      const path = document.querySelector("svg path");
      expect(path).toHaveAttribute("d", "M5 13l4 4L19 7");
    });
  });
});
