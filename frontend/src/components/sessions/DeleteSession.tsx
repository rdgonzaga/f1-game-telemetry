import { useState } from "react";

import { api } from "@/api/client";
import { Button } from "@/components/ui/button";

/** Two clicks, the second on a red button, so a stray click can't lose a session. No browser dialog. */
export function DeleteSession({ sessionId, onDeleted }: { sessionId: string; onDeleted: () => void }) {
  const [step, setStep] = useState<"idle" | "confirm" | "deleting">("idle");
  const [failed, setFailed] = useState<string | null>(null);

  if (step === "idle") {
    return (
      <Button variant="outline" onClick={() => setStep("confirm")}>
        Delete
      </Button>
    );
  }

  const remove = () => {
    setStep("deleting");
    setFailed(null);
    api.deleteSession(sessionId).then(onDeleted, (error: unknown) => {
      setFailed(error instanceof Error ? error.message : String(error));
      setStep("confirm");
    });
  };

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        <Button variant="ghost" disabled={step === "deleting"} onClick={() => setStep("idle")}>
          Cancel
        </Button>
        <Button variant="destructive" disabled={step === "deleting"} onClick={remove}>
          Delete session and laps
        </Button>
      </div>
      {failed && <p className="text-sm text-critical">Couldn&rsquo;t delete: {failed}</p>}
    </div>
  );
}
