import { fireEvent, render, screen } from "@testing-library/react";

import { App } from "./App";

function setupFetchMock(setupComplete = false) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (input === "/api/v1/setup/status") {
      return new Response(
        JSON.stringify({
          setup_complete: setupComplete,
          owner: setupComplete ? { email: "owner@example.com" } : null,
        }),
        { headers: { "Content-Type": "application/json" }, status: 200 },
      );
    }

    if (input === "/api/v1/setup/owner" && init?.method === "POST") {
      return new Response(
        JSON.stringify({
          setup_complete: true,
          owner: { email: "owner@example.com" },
        }),
        { headers: { "Content-Type": "application/json" }, status: 201 },
      );
    }

    return new Response("Not found", { status: 404 });
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  window.history.pushState({}, "", "/");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("renders the dashboard shell with primary sections", () => {
  render(<App />);

  expect(screen.getByRole("heading", { name: "Passport Auth" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Deploy your auth surface" })).toBeInTheDocument();
  expect(screen.getByText("Owner setup required")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Setup" })).toHaveAttribute("href", "/setup");
  expect(screen.getByRole("link", { name: "Users" })).toHaveAttribute("href", "/users");
  expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
  expect(screen.getByRole("link", { name: "Analytics" })).toHaveAttribute("href", "/analytics");
  expect(screen.getByRole("link", { name: "Configure setup" })).toHaveAttribute("href", "/setup");
  expect(screen.queryByRole("region", { name: "Auth surface" })).not.toBeInTheDocument();
  expect(screen.queryByText("Public web")).not.toBeInTheDocument();
  expect(screen.queryByText("localhost:8000")).not.toBeInTheDocument();
});

test("renders the setup form on the setup route", () => {
  window.history.pushState({}, "", "/setup");
  setupFetchMock();

  render(<App />);

  expect(screen.getByRole("heading", { name: "Setup Passport Auth" })).toBeInTheDocument();
  expect(screen.getByLabelText("Owner email")).toBeInTheDocument();
  expect(screen.getByLabelText("Password")).toBeInTheDocument();
  expect(screen.getByLabelText("Confirm password")).toBeInTheDocument();
  expect(screen.queryByLabelText("Application domain")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Create owner account" })).toBeInTheDocument();
});

test("renders completed setup state from the setup API", async () => {
  window.history.pushState({}, "", "/setup");
  setupFetchMock(true);

  render(<App />);

  expect(await screen.findByRole("heading", { name: "Owner account created" })).toBeInTheDocument();
  expect(screen.getByText("owner@example.com")).toBeInTheDocument();
});

test("creates the owner account through the setup API and advances setup", async () => {
  window.history.pushState({}, "", "/setup");
  const fetchMock = setupFetchMock();

  render(<App />);

  fireEvent.change(screen.getByLabelText("Owner email"), {
    target: { value: "owner@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "correct-horse-battery-staple" },
  });
  fireEvent.change(screen.getByLabelText("Confirm password"), {
    target: { value: "correct-horse-battery-staple" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create owner account" }));

  expect(await screen.findByRole("heading", { name: "Owner account created" })).toBeInTheDocument();
  expect(screen.getByText("owner@example.com")).toBeInTheDocument();
  expect(screen.getByText("Email delivery can be configured later in Settings.")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith("/api/v1/setup/owner", {
    body: JSON.stringify({
      email: "owner@example.com",
      password: "correct-horse-battery-staple",
    }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
});
