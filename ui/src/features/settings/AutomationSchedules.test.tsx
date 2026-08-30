import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { AutomationSchedules } from "./AutomationSchedules";
import * as api from "../../lib/api";
import type { PipelineSchedule } from "../../types/schedules";
import type { PipelineJob } from "../../types/jobs";

vi.mock("../../lib/api", () => ({
  getSchedules: vi.fn().mockResolvedValue([]),
  createSchedule: vi.fn(),
  updateSchedule: vi.fn(),
  runScheduleNow: vi.fn(),
}));

function makeSchedule(overrides: Partial<PipelineSchedule> = {}): PipelineSchedule {
  return {
    id: 1,
    name: "Process new photos",
    operation: "full_pipeline",
    expression: "0 * * * *",
    timezone_name: "UTC",
    enabled: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    next_run_at: null,
    last_run_at: null,
    last_run_result: null,
    ...overrides,
  };
}

function makeJob(overrides: Partial<PipelineJob> = {}): PipelineJob {
  return {
    id: 42,
    operation: "full_pipeline",
    status: "pending",
    progress_current: 0,
    progress_total: null,
    progress_message: null,
    error_message: null,
    cancel_requested: false,
    created_at: "2026-01-01T00:00:00Z",
    started_at: null,
    completed_at: null,
    ...overrides,
  };
}

async function expandSection(name: RegExp) {
  fireEvent.click(await screen.findByRole("button", { name }));
}

describe("AutomationSchedules", () => {
  it("shows one collapsible section per pre-configured operation", async () => {
    render(<AutomationSchedules />);

    expect(await screen.findByText("Process new photos")).toBeInTheDocument();
    expect(screen.getByText("Reclassify with reviewed examples")).toBeInTheDocument();
    expect(screen.getByText("Learn from reviewed examples")).toBeInTheDocument();
    expect(screen.getByText("Publish labels back to Immich")).toBeInTheDocument();
  });

  it("hides the cron field and toggle until a section is expanded", async () => {
    render(<AutomationSchedules />);

    await screen.findByText("Process new photos");

    expect(screen.queryByLabelText("Cron expression")).not.toBeInTheDocument();

    await expandSection(/Process new photos/);

    expect(await screen.findByLabelText("Cron expression")).toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: "Enable automatic processing of new photos" }),
    ).toBeInTheDocument();
  });

  it("creates a disabled schedule with the default cron the first time an operation is enabled", async () => {
    vi.mocked(api.createSchedule).mockResolvedValue(makeSchedule({ id: 5, enabled: true }));

    render(<AutomationSchedules />);

    await expandSection(/Process new photos/);

    const toggle = await screen.findByRole("switch", {
      name: "Enable automatic processing of new photos",
    });
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(api.createSchedule).toHaveBeenCalledWith({
        name: "Process new photos",
        operation: "full_pipeline",
        expression: "0 * * * *",
        enabled: true,
      });
    });

    await waitFor(() => {
      expect(toggle).toHaveAttribute("aria-checked", "true");
    });
  });

  it("updates an existing schedule's cron expression on blur", async () => {
    vi.mocked(api.getSchedules).mockResolvedValueOnce([makeSchedule()]);
    vi.mocked(api.updateSchedule).mockResolvedValue(makeSchedule({ expression: "0 4 * * *" }));

    render(<AutomationSchedules />);

    await expandSection(/Process new photos/);

    const cronField = await screen.findByLabelText("Cron expression");
    fireEvent.change(cronField, { target: { value: "0 4 * * *" } });
    fireEvent.blur(cronField);

    await waitFor(() => {
      expect(api.updateSchedule).toHaveBeenCalledWith(1, { expression: "0 4 * * *" });
    });
  });

  it("shows an inline error and keeps the edited value when the cron update is rejected", async () => {
    vi.mocked(api.getSchedules).mockResolvedValueOnce([makeSchedule()]);
    vi.mocked(api.updateSchedule).mockRejectedValue(new Error("Invalid schedule expression"));

    render(<AutomationSchedules />);

    await expandSection(/Process new photos/);

    const cronField = await screen.findByLabelText("Cron expression");
    fireEvent.change(cronField, { target: { value: "not a cron" } });
    fireEvent.blur(cronField);

    expect(await screen.findByText("Invalid schedule expression")).toBeInTheDocument();
    expect(cronField).toHaveValue("not a cron");
  });

  it("disables Run Now until a schedule exists, then queues a job", async () => {
    vi.mocked(api.getSchedules).mockResolvedValueOnce([makeSchedule({ id: 7 })]);
    vi.mocked(api.runScheduleNow).mockResolvedValue(makeJob({ id: 42 }));

    render(<AutomationSchedules />);

    await expandSection(/Process new photos/);

    const runButton = await screen.findByRole("button", { name: "Run Now" });
    expect(runButton).toBeEnabled();

    fireEvent.click(runButton);

    expect(await screen.findByText("Queued job #42.")).toBeInTheDocument();
    expect(api.runScheduleNow).toHaveBeenCalledWith(7);
  });

  it("disables Run Now when no schedule row exists yet for the operation", async () => {
    render(<AutomationSchedules />);

    await expandSection(/Process new photos/);

    expect(await screen.findByRole("button", { name: "Run Now" })).toBeDisabled();
  });
});
