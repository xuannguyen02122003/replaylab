import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { makeRun, mockFetch } from "../test/fixtures";
import { RunsPage } from "./RunsPage";

const scenarios = () => ({ body: [{ name: "order_success", description: "Works.", expected_status: "ok" }] });

function renderPage() {
  return render(
    <MemoryRouter>
      <RunsPage />
    </MemoryRouter>,
  );
}

describe("RunsPage", () => {
  it("shows a loading state, then the empty state", async () => {
    mockFetch({ "/api/runs": () => ({ body: { items: [], total: 0, limit: 20, offset: 0 } }), "/api/scenarios": scenarios });
    renderPage();
    expect(screen.getByText("Loading runs")).toBeInTheDocument();
    expect(await screen.findByText("No runs recorded yet.")).toBeInTheDocument();
  });

  it("lists runs with their status and trace completeness", async () => {
    mockFetch({
      "/api/runs": () => ({
        body: { items: [makeRun(), makeRun({ id: "b1b2c3d4-0000-4000-8000-000000000000", name: "order_success", status: "ok", completeness: "incomplete" })], total: 2, limit: 20, offset: 0 },
      }),
      "/api/scenarios": scenarios,
    });
    renderPage();
    expect(await screen.findByRole("link", { name: "order_out_of_stock" })).toHaveAttribute("href", "/runs/a3b4c5d6-e7f8-4a9b-8c0d-1e2f3a4b5c6d");
    expect(within(screen.getByRole("table")).getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Incomplete trace")).toBeInTheDocument();
    expect(screen.getByText("1–2 of 2")).toBeInTheDocument();
  });

  it("shows the backend error and can retry", async () => {
    let calls = 0;
    mockFetch({
      "/api/runs": () => {
        calls += 1;
        return calls === 1
          ? { status: 500, body: { error: { code: "boom", message: "Database is locked." } } }
          : { body: { items: [], total: 0, limit: 20, offset: 0 } };
      },
      "/api/scenarios": scenarios,
    });
    renderPage();
    expect(await screen.findByText(/HTTP 500: Database is locked\./)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No runs recorded yet.")).toBeInTheDocument();
  });

  it("explains a network failure", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    renderPage();
    expect((await screen.findAllByText(/cannot reach the replaylab collector/i)).length).toBeGreaterThan(0);
  });

  it("enables comparison only when two runs are selected", async () => {
    mockFetch({
      "/api/runs": () => ({ body: { items: [makeRun(), makeRun({ id: "b1b2c3d4-0000-4000-8000-000000000000", name: "order_success" })], total: 2, limit: 20, offset: 0 } }),
      "/api/scenarios": scenarios,
    });
    renderPage();
    const button = await screen.findByRole("button", { name: /compare selected/i });
    expect(button).toBeDisabled();
    await userEvent.click(screen.getByLabelText("Select order_out_of_stock for comparison"));
    await userEvent.click(screen.getByLabelText("Select order_success for comparison"));
    expect(button).toBeEnabled();
  });
});
