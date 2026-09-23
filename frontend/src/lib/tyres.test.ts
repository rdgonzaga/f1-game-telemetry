import { expect, it } from "vitest";

import { BRAKE_BANDS, TYRE_BANDS, band, bandsFor, type TyreTokens } from "@/lib/tyres";

const tokens: TyreTokens = {
  slick: [78, 84, 96, 100],
  inter: [52, 58, 70, 73],
  wet: [64, 68, 82, 86],
  interCompound: 7,
  wetCompound: 8,
};

it("picks the band set by fitted compound, so slicks in the rain stay on slick bands", () => {
  expect(bandsFor(16, tokens)).toBe(tokens.slick);
  expect(bandsFor(7, tokens)).toBe(tokens.inter);
  // Full wets run hotter than inters: 75 C is hot on an inter and optimal on a full wet.
  expect(band(75, bandsFor(7, tokens), TYRE_BANDS)).toBe("critical");
  expect(band(75, bandsFor(8, tokens), TYRE_BANDS)).toBe("optimal");
});

it("puts a value sitting on a threshold in the band above it", () => {
  expect(band(77.9, tokens.slick, TYRE_BANDS)).toBe("cold");
  expect(band(78, tokens.slick, TYRE_BANDS)).toBe("warming");
  expect(band(100, tokens.slick, TYRE_BANDS)).toBe("critical");
  expect(band(800, [200, 800, 950], BRAKE_BANDS)).toBe("hot");
});
