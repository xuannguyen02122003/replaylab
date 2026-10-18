import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { failedRunEvents } from "../../test/fixtures";
import { EventInspector } from "./EventInspector";

describe("EventInspector", () => {
  it("asks the user to pick an event when nothing is selected", () => {
    render(<EventInspector event={null} events={failedRunEvents} onSelect={() => {}} />);
    expect(screen.getByText(/select an event/i)).toBeInTheDocument();
  });

  it("shows recorded attributes, including redacted values", () => {
    render(<EventInspector event={failedRunEvents[3]} events={failedRunEvents} onSelect={() => {}} />);
    expect(screen.getByRole("heading", { name: "inventory.reserve_stock" })).toBeInTheDocument();
    expect(screen.getByText("SKU-123")).toBeInTheDocument();
    expect(screen.getByText("[REDACTED]")).toBeInTheDocument();
  });

  it("shows the error and stack trace of an exception", () => {
    render(<EventInspector event={failedRunEvents[4]} events={failedRunEvents} onSelect={() => {}} />);
    expect(screen.getByRole("heading", { name: "OutOfStockError" })).toBeInTheDocument();
    expect(screen.getByText("Product SKU-123 has 0 units available")).toBeInTheDocument();
    expect(screen.getByText(/examples\/order_service\/inventory.py:21/)).toBeInTheDocument();
  });

  it("links a failed parent span to the exception that caused it", async () => {
    const onSelect = vi.fn();
    render(<EventInspector event={failedRunEvents[1]} events={failedRunEvents} onSelect={onSelect} />);
    await userEvent.click(screen.getByRole("button", { name: /see outofstockerror at #4/i }));
    expect(onSelect).toHaveBeenCalledWith(failedRunEvents[4]);
  });
});
