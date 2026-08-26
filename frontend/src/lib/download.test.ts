import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { downloadBlobFile, downloadTextFile } from "./download";

interface CapturedAnchor {
  element: HTMLAnchorElement;
  clickSpy: ReturnType<typeof vi.fn>;
  removeSpy: ReturnType<typeof vi.fn>;
}

function setupAnchorCapture(captured: CapturedAnchor[]) {
  vi.spyOn(document.body, "appendChild").mockImplementation((node: Node) => {
    if (node instanceof HTMLAnchorElement) {
      const anchor = node;
      const clickSpy = vi.fn();
      const removeSpy = vi.fn();
      Object.defineProperty(anchor, "click", { value: clickSpy, configurable: true });
      Object.defineProperty(anchor, "remove", { value: removeSpy, configurable: true });
      captured.push({ element: anchor, clickSpy, removeSpy });
    }
    return node;
  });
}

function defineUrlMocks() {
  const createObjectURLMock = vi.fn(() => "blob:fake-url");
  const revokeObjectURLMock = vi.fn();
  Object.defineProperty(URL, "createObjectURL", {
    value: createObjectURLMock,
    configurable: true,
    writable: true,
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    value: revokeObjectURLMock,
    configurable: true,
    writable: true,
  });
  return { createObjectURLMock, revokeObjectURLMock };
}

function utf8ByteLength(text: string): number {
  return new TextEncoder().encode(text).length;
}

describe("downloadTextFile", () => {
  let createObjectURLMock: ReturnType<typeof vi.fn>;
  let captured: CapturedAnchor[];

  beforeEach(() => {
    const mocks = defineUrlMocks();
    createObjectURLMock = mocks.createObjectURLMock;
    captured = [];
    setupAnchorCapture(captured);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("creates a Blob with the provided content and MIME type", () => {
    downloadTextFile("hello world", "test.txt", "text/plain");

    expect(createObjectURLMock).toHaveBeenCalledTimes(1);
    const blob = createObjectURLMock.mock.calls[0][0] as Blob;
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toBe("text/plain");
    expect(blob.size).toBe(utf8ByteLength("hello world"));
  });

  it("delegates the blob to downloadBlobFile with the same filename", () => {
    downloadTextFile("data", "report.csv", "text/csv");

    expect(captured).toHaveLength(1);
    expect(captured[0].element.download).toBe("report.csv");
  });

  it("handles empty content without throwing", () => {
    expect(() => downloadTextFile("", "empty.txt", "text/plain")).not.toThrow();

    const blob = createObjectURLMock.mock.calls[0][0] as Blob;
    expect(blob.size).toBe(0);
  });

  it("preserves unicode content in the blob", () => {
    downloadTextFile("你好, 世界 🌍", "unicode.txt", "text/plain;charset=utf-8");

    const blob = createObjectURLMock.mock.calls[0][0] as Blob;
    expect(blob.size).toBe(utf8ByteLength("你好, 世界 🌍"));
  });
});

describe("downloadBlobFile", () => {
  let createObjectURLMock: ReturnType<typeof vi.fn>;
  let revokeObjectURLMock: ReturnType<typeof vi.fn>;
  let captured: CapturedAnchor[];

  beforeEach(() => {
    const mocks = defineUrlMocks();
    createObjectURLMock = mocks.createObjectURLMock;
    revokeObjectURLMock = mocks.revokeObjectURLMock;
    captured = [];
    setupAnchorCapture(captured);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("creates an object URL from the provided blob", () => {
    const blob = new Blob(["payload"], { type: "application/octet-stream" });
    downloadBlobFile(blob, "export.bin");

    expect(createObjectURLMock).toHaveBeenCalledTimes(1);
    expect(createObjectURLMock).toHaveBeenCalledWith(blob);
  });

  it("sets the anchor href to the created object URL", () => {
    downloadBlobFile(new Blob(["x"]), "file.txt");

    expect(captured).toHaveLength(1);
    expect(captured[0].element.href).toBe("blob:fake-url");
  });

  it("sets the anchor download attribute to the provided filename", () => {
    downloadBlobFile(new Blob(["x"]), "export-2026-01-01.csv");

    expect(captured[0].element.download).toBe("export-2026-01-01.csv");
  });

  it("appends the anchor to the document body before clicking", () => {
    downloadBlobFile(new Blob(["x"]), "file.txt");

    expect(captured).toHaveLength(1);
    expect(captured[0].clickSpy).toHaveBeenCalledTimes(1);
  });

  it("removes the anchor from the body after clicking", () => {
    downloadBlobFile(new Blob(["x"]), "file.txt");

    expect(captured[0].removeSpy).toHaveBeenCalledTimes(1);
  });

  it("does not revoke the URL before the 1 second timeout elapses", () => {
    downloadBlobFile(new Blob(["x"]), "file.txt");

    expect(revokeObjectURLMock).not.toHaveBeenCalled();

    vi.advanceTimersByTime(999);
    expect(revokeObjectURLMock).not.toHaveBeenCalled();
  });

  it("revokes the object URL after 1 second", () => {
    downloadBlobFile(new Blob(["x"]), "file.txt");

    vi.advanceTimersByTime(1000);
    expect(revokeObjectURLMock).toHaveBeenCalledTimes(1);
    expect(revokeObjectURLMock).toHaveBeenCalledWith("blob:fake-url");
  });

  it("accepts filenames with spaces and special characters", () => {
    downloadBlobFile(new Blob(["x"]), "我的 文件 (1).csv");

    expect(captured[0].element.download).toBe("我的 文件 (1).csv");
  });

  it("accepts an empty filename without throwing", () => {
    expect(() => downloadBlobFile(new Blob(["x"]), "")).not.toThrow();
    expect(captured[0].element.download).toBe("");
  });

  it("triggers exactly one click per download call", () => {
    downloadBlobFile(new Blob(["x"]), "file.txt");
    downloadBlobFile(new Blob(["y"]), "file2.txt");

    expect(captured).toHaveLength(2);
    expect(captured[0].clickSpy).toHaveBeenCalledTimes(1);
    expect(captured[1].clickSpy).toHaveBeenCalledTimes(1);
  });
});
