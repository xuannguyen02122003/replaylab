import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { failedRunEvents, makeRun, mockFetch } from "../test/fixtures";
import { RunDetailPage } from "./RunDetailPage";

const RUN = "a3b4c5d6-e7f8-4a9b-8c0d-1e2f3a4b5c6d";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/runs/${RUN}`]}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function serve(run = makeRun(), events = failedRunEvents) {
  return mockFetch({
    [`/api/runs/${RUN}/events`]: () => ({ body: { items: events, total: events.length, limit: 1000, offset: 0 } }),
    [`/api/runs/${RUN}`]: () => ({ body: run }),
  });
}

describe("RunDetailPage", () => {
  it("renders the timeline in sequence order and inspects a clicked event", async () => {
    serve();
    renderPage();
    expect(await screen.findByRole("heading", { name: "order_out_of_stock" })).toBeInTheDocument();
    const rows = screen.getAllByRole("button", { pressed: false }).filter((b) => b.dataset.testid?.startsWith("row-"));
    expect(rows.map((r) => r.dataset.testid)).toEqual(["row-0", "row-1", "row-2", "row-3", "row-4", "row-5"]);

    await userEvent.click(screen.getByTestId("row-4"));
    expect(screen.getByRole("heading", { name: "OutOfStockError" })).toBeInTheDocument();
  });

  it("warns when the trace is incomplete", async () => {
    serve(makeRun({ completeness: "incomplete", issues: [{ code: "missing_run_finished", message: "No run.finished event." }] }));
    renderPage();
    expect(await screen.findByText(/this trace is incomplete/i)).toBeInTheDocument();
    expect(screen.getByText("No run.finished event.")).toBeInTheDocument();
  });

  it("filters to errors only", async () => {
    serve();
    renderPage();
    await userEvent.click(await screen.findByLabelText("Errors only"));
    expect(screen.getByText("Showing 4 of 6 events")).toBeInTheDocument();
    expect(screen.queryByTestId("row-2")).not.toBeInTheDocument();
  });

  it("shows a clear empty state when filters hide everything", async () => {
    serve();
    renderPage();
    await userEvent.type(await screen.findByPlaceholderText("Search operations"), "nothing-matches");
    expect(screen.getByText("No events match these filters.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByText("Showing 6 of 6 events")).toBeInTheDocument();
  });

  it("replays recorded events step by step", async () => {
    serve();
    renderPage();
    await screen.findByRole("heading", { name: "order_out_of_stock" });

    await userEvent.click(screen.getByRole("button", { name: "Next event" }));
    expect(screen.getByTestId("row-0")).toHaveAttribute("aria-current", "step");
    expect(screen.getByText(/the original program is not run again/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Next event" }));
    await userEvent.click(screen.getByRole("button", { name: "Next event" }));
    expect(screen.getByTestId("row-2")).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "3");
    expect(screen.getByRole("heading", { name: "validate_order" })).toBeInTheDocument(); // inspector follows

    await userEvent.click(screen.getByRole("button", { name: "Previous event" }));
    expect(screen.getByTestId("row-1")).toHaveAttribute("aria-current", "step");
  });

  it("plays automatically on a timer", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    serve();
    renderPage();
    await screen.findByRole("heading", { name: "order_out_of_stock" });

    await userEvent.click(screen.getByRole("button", { name: "Play" }));
    expect(screen.getByTestId("row-0")).toHaveAttribute("aria-current", "step");
    await act(async () => {
      vi.advanceTimersByTime(700 * 2);
    });
    expect(screen.getByTestId("row-2")).toHaveAttribute("aria-current", "step");
  });

  it("shows not found for an unknown run", async () => {
    mockFetch({ "/api/runs/": () => ({ status: 404, body: { error: { code: "not_found", message: "run not found" } } }) });
    renderPage();
    expect(await screen.findByText("Run not found.")).toBeInTheDocument();
  });
});
