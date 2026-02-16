import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Badge, badgeVariants } from "@/components/ui/badge";

describe("Button component", () => {
  it("renders with default variant and size", () => {
    render(<Button>Click me</Button>);
    const button = screen.getByRole("button", { name: "Click me" });
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute("data-slot", "button");
  });

  it("renders as a button element by default", () => {
    render(<Button>Test</Button>);
    const button = screen.getByRole("button", { name: "Test" });
    expect(button.tagName).toBe("BUTTON");
  });

  it("applies custom className", () => {
    render(<Button className="custom-class">Styled</Button>);
    const button = screen.getByRole("button", { name: "Styled" });
    expect(button.className).toContain("custom-class");
  });

  it("forwards disabled prop", () => {
    render(<Button disabled>Disabled</Button>);
    const button = screen.getByRole("button", { name: "Disabled" });
    expect(button).toBeDisabled();
  });

  it("forwards onClick handler", () => {
    let clicked = false;
    render(<Button onClick={() => { clicked = true; }}>Click</Button>);
    const button = screen.getByRole("button", { name: "Click" });
    button.click();
    expect(clicked).toBe(true);
  });

  it("renders children content", () => {
    render(
      <Button>
        <span>Icon</span> Text
      </Button>
    );
    expect(screen.getByText("Icon")).toBeInTheDocument();
    expect(screen.getByText("Text")).toBeInTheDocument();
  });

  it("generates correct variant classes via buttonVariants", () => {
    const defaultClasses = buttonVariants({ variant: "default" });
    expect(defaultClasses).toContain("bg-primary");

    const destructiveClasses = buttonVariants({ variant: "destructive" });
    expect(destructiveClasses).toContain("bg-destructive");

    const outlineClasses = buttonVariants({ variant: "outline" });
    expect(outlineClasses).toContain("border");

    const ghostClasses = buttonVariants({ variant: "ghost" });
    expect(ghostClasses).toContain("hover:bg-accent");

    const linkClasses = buttonVariants({ variant: "link" });
    expect(linkClasses).toContain("underline-offset-4");
  });

  it("generates correct size classes via buttonVariants", () => {
    const smClasses = buttonVariants({ size: "sm" });
    expect(smClasses).toContain("h-8");

    const lgClasses = buttonVariants({ size: "lg" });
    expect(lgClasses).toContain("h-10");

    const iconClasses = buttonVariants({ size: "icon" });
    expect(iconClasses).toContain("size-9");
  });
});

describe("Input component", () => {
  it("renders an input element", () => {
    render(<Input placeholder="Enter text" />);
    const input = screen.getByPlaceholderText("Enter text");
    expect(input).toBeInTheDocument();
    expect(input.tagName).toBe("INPUT");
  });

  it("sets the data-slot attribute", () => {
    render(<Input placeholder="test" />);
    const input = screen.getByPlaceholderText("test");
    expect(input).toHaveAttribute("data-slot", "input");
  });

  it("forwards type prop", () => {
    render(<Input type="email" placeholder="Email" />);
    const input = screen.getByPlaceholderText("Email");
    expect(input).toHaveAttribute("type", "email");
  });

  it("applies custom className", () => {
    render(<Input className="my-class" placeholder="styled" />);
    const input = screen.getByPlaceholderText("styled");
    expect(input.className).toContain("my-class");
  });

  it("forwards disabled prop", () => {
    render(<Input disabled placeholder="disabled" />);
    const input = screen.getByPlaceholderText("disabled");
    expect(input).toBeDisabled();
  });

  it("forwards required prop", () => {
    render(<Input required placeholder="required" />);
    const input = screen.getByPlaceholderText("required");
    expect(input).toBeRequired();
  });
});

describe("Alert component", () => {
  it("renders with role=alert", () => {
    render(<Alert>Alert content</Alert>);
    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
  });

  it("sets the data-slot attribute", () => {
    render(<Alert>Content</Alert>);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("data-slot", "alert");
  });

  it("renders AlertTitle", () => {
    render(
      <Alert>
        <AlertTitle>Warning</AlertTitle>
      </Alert>
    );
    expect(screen.getByText("Warning")).toBeInTheDocument();
    expect(screen.getByText("Warning")).toHaveAttribute(
      "data-slot",
      "alert-title"
    );
  });

  it("renders AlertDescription", () => {
    render(
      <Alert>
        <AlertDescription>Something happened</AlertDescription>
      </Alert>
    );
    expect(screen.getByText("Something happened")).toBeInTheDocument();
    expect(screen.getByText("Something happened")).toHaveAttribute(
      "data-slot",
      "alert-description"
    );
  });

  it("applies custom className to Alert", () => {
    render(<Alert className="my-alert">Content</Alert>);
    const alert = screen.getByRole("alert");
    expect(alert.className).toContain("my-alert");
  });
});

describe("Badge component", () => {
  it("renders a span element by default", () => {
    render(<Badge>New</Badge>);
    const badge = screen.getByText("New");
    expect(badge.tagName).toBe("SPAN");
  });

  it("sets the data-slot attribute", () => {
    render(<Badge>Tag</Badge>);
    const badge = screen.getByText("Tag");
    expect(badge).toHaveAttribute("data-slot", "badge");
  });

  it("applies custom className", () => {
    render(<Badge className="custom">Label</Badge>);
    const badge = screen.getByText("Label");
    expect(badge.className).toContain("custom");
  });

  it("generates correct variant classes via badgeVariants", () => {
    const defaultClasses = badgeVariants({ variant: "default" });
    expect(defaultClasses).toContain("bg-primary");

    const secondaryClasses = badgeVariants({ variant: "secondary" });
    expect(secondaryClasses).toContain("bg-secondary");

    const destructiveClasses = badgeVariants({ variant: "destructive" });
    expect(destructiveClasses).toContain("bg-destructive");

    const outlineClasses = badgeVariants({ variant: "outline" });
    expect(outlineClasses).toContain("text-foreground");
  });

  it("renders children", () => {
    render(<Badge>Beta</Badge>);
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });
});
