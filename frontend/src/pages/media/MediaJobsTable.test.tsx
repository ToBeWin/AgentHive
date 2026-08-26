import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { MediaGenerationJobResponse } from "../../lib/api";
import { MediaJobsTable } from "./MediaJobsTable";

vi.mock("../../i18n-context", () => ({
  useLocale: () => ({
    locale: "en-US",
    setLocale: vi.fn(),
    t: (key: string) => key,
  }),
}));

const job: MediaGenerationJobResponse = {
  agent_id: null,
  completed_at: null,
  conversation_id: null,
  created_at: "2026-01-01T00:00:00Z",
  department_id: null,
  error_message: null,
  external_job_id: null,
  id: "abcdefgh-1234-5678-9012-abcdefghijkl",
  kind: "image",
  metadata: {},
  mode: "manual_prompt",
  model_key: "image-model",
  negative_prompt: null,
  normalized_parameters: {},
  output_storage: {},
  outputs: [],
  prompt: "Create a product image",
  provider_key: "provider-1",
  provider_type: "openai_images",
  reference_assets: [],
  request_id: "request-1",
  request_parameters: {},
  routing_key: "image-default",
  started_at: null,
  status: "queued",
  tenant_id: "tenant-1",
  updated_at: "2026-01-01T00:00:00Z",
  user_id: "user-1",
};

function renderTable(canOperateJobs: boolean) {
  const callbacks = {
    onCancel: vi.fn(),
    onEnqueue: vi.fn(),
    onPoll: vi.fn(),
    onPollBatch: vi.fn(),
    onPollEnqueue: vi.fn(),
    onRefresh: vi.fn(),
    onRetry: vi.fn(),
    onRun: vi.fn(),
    onSelect: vi.fn(),
  };
  render(
    <MediaJobsTable
      actionJobId={null}
      canOperateJobs={canOperateJobs}
      error={null}
      jobs={[job]}
      loading={false}
      refreshState=""
      selectedJobId={null}
      {...callbacks}
    />,
  );
  return callbacks;
}

describe("MediaJobsTable job details control", () => {
  it("provides an explicit focusable button with a contextual accessible name", () => {
    renderTable(true);

    const detailsButton = screen.getByRole("button", {
      name: "mediaViewDetails: mediaKindImage abcdefgh",
    });

    expect(detailsButton).toHaveAttribute("type", "button");
    expect(detailsButton).toHaveTextContent("mediaViewDetails");
    detailsButton.focus();
    expect(detailsButton).toHaveFocus();
  });

  it("selects the job when the details button is clicked", () => {
    const { onSelect } = renderTable(false);
    const detailsButton = screen.getByRole("button", {
      name: "mediaViewDetails: mediaKindImage abcdefgh",
    });

    fireEvent.click(detailsButton);

    expect(onSelect).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith(job);
  });

  it("selects the job when Enter activates the focused details button", () => {
    const { onSelect } = renderTable(true);
    const detailsButton = screen.getByRole("button", {
      name: "mediaViewDetails: mediaKindImage abcdefgh",
    });
    detailsButton.focus();

    fireEvent.keyDown(detailsButton, { code: "Enter", key: "Enter" });

    expect(onSelect).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith(job);
  });
});
