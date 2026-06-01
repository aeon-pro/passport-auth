import { render, screen } from "@testing-library/react";

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
  expect(screen.getByLabelText("Application domain")).toBeInTheDocument();
  expect(screen.getByLabelText("Auth domain")).toBeInTheDocument();
  expect(screen.getByLabelText("Allowed redirect URL")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Continue setup" })).toBeInTheDocument();
});
