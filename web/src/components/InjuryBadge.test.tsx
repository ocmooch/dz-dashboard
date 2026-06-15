import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { InjuryBadge } from "./InjuryBadge";

describe("InjuryBadge", () => {
  it("shortens Questionable and shows primary body part + practice code", () => {
    render(<InjuryBadge status="Questionable" bodyPart="Knee" practiceStatus="Ltd" />);
    expect(screen.getByText("Q · Knee · Ltd")).toBeInTheDocument();
  });

  it("joins primary and secondary body parts inline", () => {
    render(
      <InjuryBadge status="Out" bodyPart="Hamstring" secondary="Back" practiceStatus="DNP" />,
    );
    expect(screen.getByText("Out · Hamstring/Back · DNP")).toBeInTheDocument();
  });

  it("does not repeat an 'Out' practice code behind an 'Out' status", () => {
    render(<InjuryBadge status="Out" bodyPart="Calf" practiceStatus="Out" />);
    expect(screen.getByText("Out · Calf")).toBeInTheDocument();
  });

  it("renders a full-sentence tooltip with the practice phrase", () => {
    render(<InjuryBadge status="Questionable" bodyPart="Knee" practiceStatus="Ltd" />);
    expect(screen.getByText("Q · Knee · Ltd")).toHaveAttribute(
      "title",
      "Questionable — Knee. Limited participation in practice.",
    );
  });

  it("handles a status with no body part", () => {
    render(<InjuryBadge status="Doubtful" />);
    const el = screen.getByText("D");
    expect(el).toBeInTheDocument();
    expect(el).toHaveAttribute("title", "Doubtful.");
  });
});
