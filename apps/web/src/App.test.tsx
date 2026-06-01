import { fireEvent, render, screen } from "@testing-library/react";

import { App } from "./App";

beforeEach(() => {
  window.history.pushState({}, "", "/");
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

  render(<App />);

  expect(screen.getByRole("heading", { name: "Setup Passport Auth" })).toBeInTheDocument();
  expect(screen.getByLabelText("Owner email")).toBeInTheDocument();
  expect(screen.getByLabelText("Password")).toBeInTheDocument();
  expect(screen.getByLabelText("Confirm password")).toBeInTheDocument();
  expect(screen.queryByLabelText("Application domain")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Create owner account" })).toBeInTheDocument();
});

test("creates the owner account locally and advances setup", () => {
  window.history.pushState({}, "", "/setup");

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

  expect(screen.getByRole("heading", { name: "Owner account created" })).toBeInTheDocument();
  expect(screen.getByText("owner@example.com")).toBeInTheDocument();
  expect(screen.getByText("Email delivery can be configured later in Settings.")).toBeInTheDocument();
});
