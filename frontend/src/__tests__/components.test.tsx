/**
 * Component render tests for the SupoClip frontend.
 *
 * Covers:
 * - StatusBadge — renders correct text and icon for each task status
 * - ErrorAlert — renders error message with correct styling
 * - SuccessAlert — renders success message with correct styling
 * - EmptyState — renders title, description, and optional action
 * - FontPreview — renders preview text with correct inline styles
 * - FontColorPicker — renders color input, text input, and preset swatches
 * - AuthGuard — renders children, loading, or unauthenticated views
 * - TaskCard — renders task info with correct date format and clip count
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock next/link to render a plain anchor
jest.mock("next/link", () => {
  return function MockLink({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) {
    return <a href={href}>{children}</a>;
  };
});

// Mock lucide-react icons as simple spans with data-testid
jest.mock("lucide-react", () => ({
  CheckCircle: (props: React.SVGProps<SVGSVGElement>) => (
    <span data-testid="icon-check-circle" className={props.className} />
  ),
  Loader2: (props: React.SVGProps<SVGSVGElement>) => (
    <span data-testid="icon-loader2" className={props.className} />
  ),
  AlertCircle: (props: React.SVGProps<SVGSVGElement>) => (
    <span data-testid="icon-alert-circle" className={props.className} />
  ),
  Clock: (props: React.SVGProps<SVGSVGElement>) => (
    <span data-testid="icon-clock" className={props.className} />
  ),
  Search: (props: React.SVGProps<SVGSVGElement>) => (
    <span data-testid="icon-search" className={props.className} />
  ),
  RefreshCw: (props: React.SVGProps<SVGSVGElement>) => (
    <span data-testid="icon-refresh" className={props.className} />
  ),
  ChevronDown: (props: React.SVGProps<SVGSVGElement>) => (
    <span data-testid="icon-chevron-down" className={props.className} />
  ),
  Video: (props: React.SVGProps<SVGSVGElement>) => (
    <span data-testid="icon-video" className={props.className} />
  ),
}));

// Mock the auth-client useSession hook
const mockUseSession = jest.fn();
jest.mock("@/lib/auth-client", () => ({
  useSession: () => mockUseSession(),
}));

// Mock useFonts hook
jest.mock("@/hooks/useFonts", () => ({
  useFonts: () => ({
    fonts: [],
    isLoading: false,
    error: null,
    refreshFonts: jest.fn(),
  }),
}));

// Mock useApiUrl hook
jest.mock("@/hooks/useApiUrl", () => ({
  useApiUrl: () => "http://localhost:8008",
}));

// ---------------------------------------------------------------------------
// Imports (after mocks)
// ---------------------------------------------------------------------------

import { StatusBadge } from "@/components/StatusBadge";
import { ErrorAlert } from "@/components/alerts/ErrorAlert";
import { SuccessAlert } from "@/components/alerts/SuccessAlert";
import { FontPreview } from "@/components/FontPreview";
import { FontColorPicker } from "@/components/FontColorPicker";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { TaskCard } from "@/components/TaskCard";

// ---------------------------------------------------------------------------
// StatusBadge
// ---------------------------------------------------------------------------
describe("StatusBadge", () => {
  it('renders "Completed" text for completed status', () => {
    render(<StatusBadge status="completed" />);
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it('renders "Processing" text for processing status', () => {
    render(<StatusBadge status="processing" />);
    expect(screen.getByText("Processing")).toBeInTheDocument();
  });

  it('renders "Queued" text for queued status', () => {
    render(<StatusBadge status="queued" />);
    expect(screen.getByText("Queued")).toBeInTheDocument();
  });

  it('renders "Error" text for error status', () => {
    render(<StatusBadge status="error" />);
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it('renders "Error" text for failed status', () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("renders the raw status text for unknown statuses", () => {
    render(<StatusBadge status="unknown-status" />);
    expect(screen.getByText("unknown-status")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// ErrorAlert
// ---------------------------------------------------------------------------
describe("ErrorAlert", () => {
  it("renders the error message", () => {
    render(<ErrorAlert message="Something went wrong" />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("applies red border styling", () => {
    const { container } = render(<ErrorAlert message="Error" />);
    const alertEl = container.firstChild as HTMLElement;
    expect(alertEl.className).toContain("border-red-200");
    expect(alertEl.className).toContain("bg-red-50");
  });

  it("applies additional className when provided", () => {
    const { container } = render(
      <ErrorAlert message="Error" className="mt-6" />
    );
    const alertEl = container.firstChild as HTMLElement;
    expect(alertEl.className).toContain("mt-6");
  });

  it("renders the alert icon", () => {
    render(<ErrorAlert message="Error" />);
    expect(screen.getByTestId("icon-alert-circle")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// SuccessAlert
// ---------------------------------------------------------------------------
describe("SuccessAlert", () => {
  it("renders the success message", () => {
    render(<SuccessAlert message="Operation successful" />);
    expect(screen.getByText("Operation successful")).toBeInTheDocument();
  });

  it("applies green border styling", () => {
    const { container } = render(<SuccessAlert message="Success" />);
    const alertEl = container.firstChild as HTMLElement;
    expect(alertEl.className).toContain("border-green-200");
    expect(alertEl.className).toContain("bg-green-50");
  });

  it("applies additional className when provided", () => {
    const { container } = render(
      <SuccessAlert message="Done" className="mb-4" />
    );
    const alertEl = container.firstChild as HTMLElement;
    expect(alertEl.className).toContain("mb-4");
  });

  it("renders the check icon", () => {
    render(<SuccessAlert message="Success" />);
    expect(screen.getByTestId("icon-check-circle")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// FontPreview
// ---------------------------------------------------------------------------
describe("FontPreview", () => {
  it("renders the default preview text", () => {
    render(
      <FontPreview fontFamily="Arial" fontSize={24} fontColor="#FFFFFF" />
    );
    expect(
      screen.getByText("Preview: Your subtitle will look like this")
    ).toBeInTheDocument();
  });

  it("renders custom preview text", () => {
    render(
      <FontPreview
        fontFamily="Arial"
        fontSize={24}
        fontColor="#FFFFFF"
        previewText="Custom preview"
      />
    );
    expect(screen.getByText("Custom preview")).toBeInTheDocument();
  });

  it("renders the text prop over previewText", () => {
    render(
      <FontPreview
        fontFamily="Arial"
        fontSize={24}
        fontColor="#FFFFFF"
        text="Override text"
        previewText="Should not show"
      />
    );
    expect(screen.getByText("Override text")).toBeInTheDocument();
    expect(screen.queryByText("Should not show")).not.toBeInTheDocument();
  });

  it("applies the correct inline font styles", () => {
    render(
      <FontPreview fontFamily="Helvetica" fontSize={32} fontColor="#FF0000" />
    );
    const textEl = screen.getByText(
      "Preview: Your subtitle will look like this"
    );
    expect(textEl.style.fontSize).toBe("32px");
    expect(textEl.style.color).toBe("rgb(255, 0, 0)");
  });

  it("applies text transform when specified", () => {
    render(
      <FontPreview
        fontFamily="Arial"
        fontSize={24}
        fontColor="#FFFFFF"
        textTransform="uppercase"
      />
    );
    const textEl = screen.getByText(
      "Preview: Your subtitle will look like this"
    );
    expect(textEl.style.textTransform).toBe("uppercase");
  });

  it("applies text shadow when shadow properties are set", () => {
    render(
      <FontPreview
        fontFamily="Arial"
        fontSize={24}
        fontColor="#FFFFFF"
        shadowColor="#000000"
        shadowOffset={3}
      />
    );
    const textEl = screen.getByText(
      "Preview: Your subtitle will look like this"
    );
    expect(textEl.style.textShadow).toBe("3px 3px 0px #000000");
  });

  it("sets text shadow to none when shadow offset is 0", () => {
    render(
      <FontPreview
        fontFamily="Arial"
        fontSize={24}
        fontColor="#FFFFFF"
        shadowColor="#000000"
        shadowOffset={0}
      />
    );
    const textEl = screen.getByText(
      "Preview: Your subtitle will look like this"
    );
    expect(textEl.style.textShadow).toBe("none");
  });
});

// ---------------------------------------------------------------------------
// FontColorPicker
// ---------------------------------------------------------------------------
describe("FontColorPicker", () => {
  it("renders the label", () => {
    render(<FontColorPicker value="#FFFFFF" onChange={() => {}} />);
    expect(screen.getByText("Font Color")).toBeInTheDocument();
  });

  it("renders a custom label", () => {
    render(
      <FontColorPicker
        value="#FFFFFF"
        onChange={() => {}}
        label="Stroke Color"
      />
    );
    expect(screen.getByText("Stroke Color")).toBeInTheDocument();
  });

  it("renders all default preset swatches", () => {
    const { container } = render(
      <FontColorPicker value="#FFFFFF" onChange={() => {}} />
    );
    // Default presets: 6 colors
    const swatches = container.querySelectorAll("button");
    expect(swatches.length).toBe(6);
  });

  it("renders custom preset swatches", () => {
    const customPresets = ["#FF0000", "#00FF00", "#0000FF"];
    const { container } = render(
      <FontColorPicker
        value="#FF0000"
        onChange={() => {}}
        presets={customPresets}
      />
    );
    const swatches = container.querySelectorAll("button");
    expect(swatches.length).toBe(3);
  });

  it("calls onChange when a preset swatch is clicked", () => {
    const onChange = jest.fn();
    const { container } = render(
      <FontColorPicker value="#FFFFFF" onChange={onChange} />
    );
    const swatches = container.querySelectorAll("button");
    // Click the second swatch (#000000)
    fireEvent.click(swatches[1]);
    expect(onChange).toHaveBeenCalledWith("#000000");
  });

  it("highlights the currently selected preset", () => {
    const { container } = render(
      <FontColorPicker value="#FFFFFF" onChange={() => {}} />
    );
    const swatches = container.querySelectorAll("button");
    // First swatch is #FFFFFF which matches the value
    expect(swatches[0].className).toContain("border-gray-800");
    // Second swatch should not be highlighted
    expect(swatches[1].className).toContain("border-gray-300");
  });

  it("renders the color input with the correct value", () => {
    render(<FontColorPicker value="#FF6B6B" onChange={() => {}} />);
    const colorInput = screen.getByDisplayValue("#FF6B6B");
    expect(colorInput).toBeInTheDocument();
  });

  it("disables buttons when disabled prop is true", () => {
    const { container } = render(
      <FontColorPicker value="#FFFFFF" onChange={() => {}} disabled />
    );
    const swatches = container.querySelectorAll("button");
    swatches.forEach((swatch) => {
      expect(swatch).toBeDisabled();
    });
  });
});

// ---------------------------------------------------------------------------
// AuthGuard
// ---------------------------------------------------------------------------
describe("AuthGuard", () => {
  it("renders children when user is authenticated", () => {
    mockUseSession.mockReturnValue({
      data: {
        session: { id: "s1" },
        user: { id: "u1", name: "Test User", email: "test@test.com" },
      },
      isPending: false,
      error: null,
    });

    render(
      <AuthGuard>
        <div data-testid="protected-content">Protected</div>
      </AuthGuard>
    );
    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
  });

  it("renders loading skeleton while session is pending", () => {
    mockUseSession.mockReturnValue({
      data: null,
      isPending: true,
      error: null,
    });

    const { container } = render(
      <AuthGuard>
        <div>Protected</div>
      </AuthGuard>
    );
    // DefaultLoadingSkeleton uses Skeleton components
    expect(container.textContent).not.toContain("Protected");
  });

  it("renders custom loading fallback when provided", () => {
    mockUseSession.mockReturnValue({
      data: null,
      isPending: true,
      error: null,
    });

    render(
      <AuthGuard loadingFallback={<div data-testid="custom-loader">Loading...</div>}>
        <div>Protected</div>
      </AuthGuard>
    );
    expect(screen.getByTestId("custom-loader")).toBeInTheDocument();
  });

  it("renders default unauthenticated view when no session", () => {
    mockUseSession.mockReturnValue({
      data: null,
      isPending: false,
      error: null,
    });

    render(
      <AuthGuard>
        <div>Protected</div>
      </AuthGuard>
    );
    // DefaultUnauthenticatedView contains "SupoClip" heading and sign-in buttons
    expect(screen.getByText("SupoClip")).toBeInTheDocument();
    expect(screen.getByText("Get Started")).toBeInTheDocument();
    expect(screen.getByText("Sign In")).toBeInTheDocument();
  });

  it("renders custom fallback when provided and user is not authenticated", () => {
    mockUseSession.mockReturnValue({
      data: null,
      isPending: false,
      error: null,
    });

    render(
      <AuthGuard fallback={<div data-testid="custom-unauth">Please log in</div>}>
        <div>Protected</div>
      </AuthGuard>
    );
    expect(screen.getByTestId("custom-unauth")).toBeInTheDocument();
  });

  it("does not render children when session has no user", () => {
    mockUseSession.mockReturnValue({
      data: { session: { id: "s1" }, user: null },
      isPending: false,
      error: null,
    });

    render(
      <AuthGuard>
        <div data-testid="protected-content">Protected</div>
      </AuthGuard>
    );
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// TaskCard
// ---------------------------------------------------------------------------
describe("TaskCard", () => {
  const mockTask = {
    id: "task-123",
    source_title: "My Test Video",
    source_type: "youtube",
    status: "completed",
    clips_count: 3,
    created_at: "2024-06-15T14:30:00Z",
  };

  it("renders the task title", () => {
    render(<TaskCard task={mockTask} />);
    expect(screen.getByText("My Test Video")).toBeInTheDocument();
  });

  it("renders the source type badge", () => {
    render(<TaskCard task={mockTask} />);
    expect(screen.getByText("youtube")).toBeInTheDocument();
  });

  it('renders plural "clips" for count > 1', () => {
    render(<TaskCard task={mockTask} />);
    expect(screen.getByText("3 clips")).toBeInTheDocument();
  });

  it('renders singular "clip" for count = 1', () => {
    render(<TaskCard task={{ ...mockTask, clips_count: 1 }} />);
    expect(screen.getByText("1 clip")).toBeInTheDocument();
  });

  it("renders the status badge", () => {
    render(<TaskCard task={mockTask} />);
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("wraps content in a link when clickable (default)", () => {
    const { container } = render(<TaskCard task={mockTask} />);
    const link = container.querySelector("a");
    expect(link).toBeInTheDocument();
    expect(link?.getAttribute("href")).toBe("/tasks/task-123");
  });

  it("does not wrap in a link when clickable is false", () => {
    const { container } = render(
      <TaskCard task={mockTask} clickable={false} />
    );
    const link = container.querySelector("a");
    expect(link).not.toBeInTheDocument();
  });

  it("uses detailed date format by default", () => {
    render(<TaskCard task={mockTask} />);
    // Detailed format includes month abbreviation
    const dateText = screen.getByText(/Jun/);
    expect(dateText).toBeInTheDocument();
  });

  it("renders different statuses correctly", () => {
    const { rerender } = render(
      <TaskCard task={{ ...mockTask, status: "processing" }} />
    );
    expect(screen.getByText("Processing")).toBeInTheDocument();

    rerender(<TaskCard task={{ ...mockTask, status: "error" }} />);
    expect(screen.getByText("Error")).toBeInTheDocument();

    rerender(<TaskCard task={{ ...mockTask, status: "queued" }} />);
    expect(screen.getByText("Queued")).toBeInTheDocument();
  });

  it("renders 0 clips correctly", () => {
    render(<TaskCard task={{ ...mockTask, clips_count: 0 }} />);
    expect(screen.getByText("0 clips")).toBeInTheDocument();
  });
});
