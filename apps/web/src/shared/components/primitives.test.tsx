import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { StatePanel } from "./StatePanel";

describe("shared interface primitives", () => {
  it("keeps a disabled button non-submitting by default", () => {
    render(<Button disabled>Continue</Button>);
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
    expect(screen.getByRole("button")).toHaveAttribute("type", "button");
  });
  it("uses a live alert for an error state", () => {
    render(<StatePanel kind="error" title="Could not load">Try again later.</StatePanel>);
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load");
  });
  it("renders a semantic badge label without color-only meaning", () => {
    render(<Badge tone="success">Verified</Badge>);
    expect(screen.getByText("Verified")).toBeInTheDocument();
  });
});
