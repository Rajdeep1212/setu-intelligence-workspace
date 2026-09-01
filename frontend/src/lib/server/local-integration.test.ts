import { describe, expect, it } from "vitest";

import { sourceThroughBff, sourcesThroughBff } from "@/lib/server/bff";

const enabled = process.env.SETU_RUN_LOCAL_INTEGRATION === "1" ? it : it.skip;

describe("opt-in local source integration", () => {
  enabled("reads bounded source metadata through the BFF without querying", async () => {
    const list = await sourcesThroughBff(new URL("http://127.0.0.1/api/sources?page=1&page_size=3&language=en"));
    expect(list.items.length).toBeGreaterThan(0);
    expect(list.items.length).toBeLessThanOrEqual(3);
    expect(list.items.every((item) => item.language === "en")).toBe(true);
    const detail = await sourceThroughBff(list.items[0].id);
    expect(detail.id).toBe(list.items[0].id);
    expect(JSON.stringify(detail)).not.toContain("raw_text");
    expect(JSON.stringify(detail)).not.toContain("content");
  });
});
