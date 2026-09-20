import { useParams } from "react-router-dom";

import { ComingIn } from "@/components/ComingIn";

export default function LapDetail() {
  const { sessionId, lapNumber } = useParams();
  return (
    <ComingIn
      title={`Lap ${lapNumber ?? "?"}`}
      issue={28}
      what={`Speed and input traces against distance for lap ${lapNumber ?? "?"} of ${sessionId ?? "a session"}.`}
    />
  );
}
