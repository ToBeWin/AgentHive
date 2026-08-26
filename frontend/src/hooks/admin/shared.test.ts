import { describe, expect, it } from "vitest";
import { loadMessages } from "../../i18n";
import { errorToMessage } from "./shared";

describe("errorToMessage", () => {
  it("does not expose raw HTTP client error details in user-facing notices", async () => {
    await loadMessages("en-US");

    expect(
      errorToMessage(
        {
          message: "HTTP 422: credential validation failed at upstream.example",
          status: 422,
        },
        "en-US",
      ),
    ).toBe("Request was invalid.");
  });

  it("keeps the client-error fallback localized", () => {
    expect(errorToMessage({ message: "HTTP 400", status: 400 }, "zh-CN")).toBe("请求参数有误。");
  });
});
