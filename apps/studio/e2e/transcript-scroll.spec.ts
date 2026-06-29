import { expect, test, type Page } from "@playwright/test";

test("transcript scrolls from first to last message without covering the composer", async ({
  page,
}) => {
  await mockStudio(page);
  await page.goto("/conversations/conv-scroll");
  const transcript = page.getByRole("region", { name: "Message transcript" });
  await expect(transcript).toBeVisible();
  await expect(page.getByLabel("Message Hephaestus")).toBeVisible();
  await expect.poll(() => transcript.evaluate((node) => node.scrollHeight > node.clientHeight)).toBe(true);
  await expect.poll(() => transcript.evaluate((node) => node.scrollHeight - node.clientHeight - node.scrollTop)).toBeLessThan(3);

  await transcript.focus();
  await page.keyboard.press("Home");
  await expect.poll(() => transcript.evaluate((node) => node.scrollTop)).toBe(0);
  await expect(transcript.getByText("First long message", { exact: true })).toBeVisible();
  await page.keyboard.press("End");
  await expect.poll(() => transcript.evaluate((node) => node.scrollHeight - node.clientHeight - node.scrollTop)).toBeLessThan(3);
  await expect(transcript.getByText("Last long message", { exact: true })).toBeVisible();

  const transcriptBox = await transcript.boundingBox();
  const composerBox = await page.locator(".composer").boundingBox();
  expect(transcriptBox && composerBox && transcriptBox.y + transcriptBox.height <= composerBox.y + 1).toBe(true);

  await page.setViewportSize({ width: 560, height: 720 });
  await expect(transcript).toBeVisible();
  await page.mouse.wheel(0, -600);
  await expect.poll(() => transcript.evaluate((node) => node.scrollTop)).toBeLessThan(
    await transcript.evaluate((node) => node.scrollHeight - node.clientHeight),
  );
});

async function mockStudio(page: Page) {
  const conversation = {
    id: "conv-scroll",
    title: "Scroll fixture",
    created_at: "2026-06-29T00:00:00Z",
    updated_at: "2026-06-29T00:00:00Z",
    mode: "balanced",
    repo_profile_id: null,
    repo_name: null,
    workspace_path: null,
    is_pinned: false,
    is_archived: false,
    last_opened_at: null,
    message_count: 32,
    last_message_preview: "Last long message",
    linked_decision_count: 0,
    coding_request_count: 0,
    validation_run_count: 0,
  };
  const messages = Array.from({ length: 32 }, (_, index) => ({
    id: `message-${index}`,
    session_id: "conv-scroll",
    role: index % 2 ? "assistant" : "user",
    content:
      index === 0
        ? `First long message\n\n${"content ".repeat(80)}`
        : index === 31
          ? `Last long message\n\n${"content ".repeat(80)}`
          : `Message ${index}\n\n${"content ".repeat(80)}`,
    created_at: "2026-06-29T00:00:00Z",
    intent: "general",
    mode: "balanced",
    provider_model: null,
    metadata: {},
  }));
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body =
      path === "/api/config"
        ? { app_name: "Hephaestus", version: "test", database_path: "", default_host: "127.0.0.1", default_port: 8741, default_url: "", static_assets_available: true, active_policy_profile: "developer", provider_label: "Local deterministic mode", local_mode_available: true }
        : path === "/api/providers/status"
          ? { active_label: "Local deterministic mode", active_provider: "local", statuses: [] }
          : path === "/api/policy/active"
            ? { id: "developer", name: "Developer", profile_type: "developer", description: "" }
            : path === "/api/modes"
              ? [{ value: "balanced", label: "Balanced", description: "" }]
              : path === "/api/repos/recent"
                ? []
                : path === "/api/conversations"
                  ? { conversations: [conversation], total: 1, limit: 120, offset: 0 }
                  : path === "/api/conversations/conv-scroll/messages"
                    ? messages
                    : path === "/api/conversations/conv-scroll"
                      ? { conversation, regular_memory_count: 0, strategic_memory_count: 0, linked_artifact_count: 0 }
                      : {};
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
  });
}
