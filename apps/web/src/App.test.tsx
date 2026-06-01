import { fireEvent, render, screen } from "@testing-library/react";

import { App } from "./App";

function setupFetchMock(options: { setupComplete?: boolean; authenticated?: boolean } = {}) {
  const { setupComplete = false, authenticated = false } = options;
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

    if (input === "/api/v1/dashboard/auth/me") {
      const hasToken = init?.headers && JSON.stringify(init.headers).includes("test-token");
      if (authenticated && hasToken) {
        return new Response(
          JSON.stringify({ email: "owner@example.com", role: "owner" }),
          { headers: { "Content-Type": "application/json" }, status: 200 },
        );
      }

      return new Response(JSON.stringify({ detail: "Not authenticated." }), {
        headers: { "Content-Type": "application/json" },
        status: 401,
      });
    }

    if (input === "/api/v1/dashboard/auth/login" && init?.method === "POST") {
      return new Response(
        JSON.stringify({
          access_token: "test-token",
          token_type: "bearer",
          user: { email: "owner@example.com", role: "owner" },
        }),
        { headers: { "Content-Type": "application/json" }, status: 200 },
      );
    }

    if (input === "/api/v1/dashboard/auth/password-reset/start" && init?.method === "POST") {
      return new Response(
        JSON.stringify({ sent: true, dev_otp: "123456" }),
        { headers: { "Content-Type": "application/json" }, status: 200 },
      );
    }

    if (input === "/api/v1/dashboard/auth/password-reset/confirm" && init?.method === "POST") {
      return new Response(
        JSON.stringify({ ok: true }),
        { headers: { "Content-Type": "application/json" }, status: 200 },
      );
    }

    return new Response("Not found", { status: 404 });
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  window.history.pushState({}, "", "/");
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

test("renders setup prompt before the owner account exists", async () => {
  setupFetchMock();

  render(<App />);

  expect(screen.getByRole("heading", { name: "Passport Auth" })).toBeInTheDocument();
  expect(await screen.findByText("Owner setup required")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Deploy your auth surface" })).toBeInTheDocument();
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
  setupFetchMock({ setupComplete: true });

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

test("protects the dashboard behind owner login after setup", async () => {
  setupFetchMock({ setupComplete: true });

  render(<App />);

  expect(await screen.findByRole("heading", { name: "Sign in to Passport Auth" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Deploy your auth surface" })).not.toBeInTheDocument();
  expect(screen.queryByText("Not configured")).not.toBeInTheDocument();
});

test("logs in with owner credentials and renders configured dashboard", async () => {
  const fetchMock = setupFetchMock({ setupComplete: true });

  render(<App />);

  fireEvent.change(await screen.findByLabelText("Email"), {
    target: { value: "owner@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "correct-horse-battery-staple" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

  expect(await screen.findByRole("heading", { name: "Deploy your auth surface" })).toBeInTheDocument();
  expect(screen.getByText("Setup complete")).toBeInTheDocument();
  expect(screen.getByText("Owner configured")).toBeInTheDocument();
  expect(screen.queryByText("Not configured")).not.toBeInTheDocument();
  expect(window.localStorage.getItem("passport-auth-token")).toBe("test-token");
  expect(fetchMock).toHaveBeenCalledWith("/api/v1/dashboard/auth/login", {
    body: JSON.stringify({
      email: "owner@example.com",
      password: "correct-horse-battery-staple",
    }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
});

test("requests and confirms password reset OTP", async () => {
  const fetchMock = setupFetchMock({ setupComplete: true });

  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: "Reset password" }));
  fireEvent.change(screen.getByLabelText("Owner email"), {
    target: { value: "owner@example.com" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send reset OTP" }));

  expect(await screen.findByText("Development OTP: 123456")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("OTP"), {
    target: { value: "123456" },
  });
  fireEvent.change(screen.getByLabelText("New password"), {
    target: { value: "new-correct-horse-battery-staple" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Update password" }));

  expect(await screen.findByText("Password updated. Sign in with the new password.")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith("/api/v1/dashboard/auth/password-reset/confirm", {
    body: JSON.stringify({
      email: "owner@example.com",
      otp: "123456",
      password: "new-correct-horse-battery-staple",
    }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
});
