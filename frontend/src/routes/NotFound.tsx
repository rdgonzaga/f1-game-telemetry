import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/Panel";

export default function NotFound() {
  return (
    <Panel title="Not found">
      <p className="text-text-3">That route does not exist.</p>
      <Button asChild className="mt-[var(--f1-space-4)]">
        <Link to="/">Back to live</Link>
      </Button>
    </Panel>
  );
}
