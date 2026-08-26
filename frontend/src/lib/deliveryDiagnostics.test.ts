import { describe, expect, it } from "vitest";
import { showDeliveryDiagnostics } from "./deliveryDiagnostics";

describe("showDeliveryDiagnostics", () => {
  it("returns true for admin workspace", () => {
    expect(showDeliveryDiagnostics("admin")).toBe(true);
  });

  it("returns false for user workspace", () => {
    expect(showDeliveryDiagnostics("user")).toBe(false);
  });
});
