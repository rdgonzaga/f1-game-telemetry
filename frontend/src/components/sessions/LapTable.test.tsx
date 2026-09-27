import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";

import type { LapSummary } from "@/api/types";
import { LapTable } from "@/components/sessions/LapTable";

const lap = (number: number, sectors: [number, number, number], extra: Partial<LapSummary> = {}): LapSummary => ({
  number,
  lap_time_ms: sectors[0] + sectors[1] + sectors[2],
  invalid: false,
  partial: false,
  samples: 5000,
  sector_times_ms: sectors,
  ...extra,
});

it("marks the best lap and each best sector, and links every lap", () => {
  const laps = [
    lap(1, [28880, 27981, 34498]),
    lap(2, [26847, 28146, 28568]),
    lap(3, [26000, 27000, 28000], { invalid: true }),
  ];
  render(
    <MemoryRouter>
      <LapTable sessionId="20260927-225841_monza_race" laps={laps} bestLap={2} />
    </MemoryRouter>,
  );

  const row = (n: number) => screen.getByRole("row", { name: new RegExp(`^Lap ${n}\\b`) });
  const best = (n: number) =>
    within(row(n))
      .queryAllByRole("cell")
      .filter((c) => c.dataset.best === "true");
  // Lap 2 is the best lap and holds S1 and S3; lap 1 holds S2. The invalid lap 3 is quicker everywhere and holds none.
  expect(best(2).map((c) => c.textContent)).toEqual(["1:23.561", "26.847", "28.568"]);
  expect(best(1).map((c) => c.textContent)).toEqual(["27.981"]);
  expect(best(3)).toEqual([]);
  expect(within(row(3)).getByText("Invalid")).toBeInTheDocument();
  expect(within(row(1)).getByRole("link")).toHaveAttribute("href", "/sessions/20260927-225841_monza_race/laps/1");
});
