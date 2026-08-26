import { describe, expect, it } from "vitest";
import { getValueAtSchemaPath } from "./schemaDescriptor";

// TEC-NATKIT-32: the Schema Inspector read "Unavailable" for every array-valued
// field. expandFieldLeaves() emits a "{index}" placeholder when it expands an
// array with no sample value to hand, and those paths were later resolved
// against real records — matching neither the numeric-index branch nor the
// object-key branch, and falling through to undefined.
describe("getValueAtSchemaPath", () => {
  const record = {
    accel_x: [1, 2, 3],
    device_ts_us: 1787681323331568,
    nested: { samples: [{ v: 10 }, { v: 20 }] },
    empty: [],
    scalar: 5,
  };

  it("returns the whole record for an empty path", () => {
    expect(getValueAtSchemaPath(record, "")).toBe(record);
  });

  it("walks object keys", () => {
    expect(getValueAtSchemaPath(record, "device_ts_us")).toBe(1787681323331568);
  });

  it("walks numeric indices", () => {
    expect(getValueAtSchemaPath(record, "accel_x.1")).toBe(2);
  });

  // The regression this file exists for.
  it("resolves a {index} placeholder to the LAST element", () => {
    // Last rather than first: the live readouts rendered beside this panel show
    // the newest sample, and an inspector disagreeing with the number next to
    // it is worse than one that says nothing.
    expect(getValueAtSchemaPath(record, "accel_x.{index}")).toBe(3);
  });

  it("resolves a placeholder mid-path", () => {
    expect(getValueAtSchemaPath(record, "nested.samples.{index}.v")).toBe(20);
  });

  it("matches any {...} spelling, not just {index}", () => {
    // So a future placeholder name degrades to this branch rather than silently
    // reverting to "Unavailable".
    expect(getValueAtSchemaPath(record, "accel_x.{i}")).toBe(3);
    expect(getValueAtSchemaPath(record, "accel_x.{}")).toBe(3);
  });

  it("returns undefined for a placeholder on an empty array", () => {
    expect(getValueAtSchemaPath(record, "empty.{index}")).toBeUndefined();
  });

  it("returns undefined for a placeholder on a non-array", () => {
    expect(getValueAtSchemaPath(record, "scalar.{index}")).toBeUndefined();
  });

  it("does not treat a literal brace-free key as a placeholder", () => {
    expect(getValueAtSchemaPath({ index: 7 }, "index")).toBe(7);
  });

  it("returns undefined rather than throwing on a missing key", () => {
    expect(getValueAtSchemaPath(record, "nope.deeper")).toBeUndefined();
  });

  it("returns undefined for a numeric index into a non-array", () => {
    expect(getValueAtSchemaPath(record, "scalar.0")).toBeUndefined();
  });
});
