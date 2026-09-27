import { useState, type FormEvent } from "react";

import type { SettingsChange, SettingsResult, SetupInfo } from "@/api/types";
import { Panel } from "@/components/Panel";
import { Button } from "@/components/ui/button";
import { saveSettings, useSetup, useSetupPoll } from "@/live/setup";
import { useLiveStatus } from "@/live/useLive";
import { cn } from "@/lib/utils";

type Platform = "pc" | "ps5" | "xbox";

const PLATFORMS: { id: Platform; label: string }[] = [
  { id: "pc", label: "PC" },
  { id: "ps5", label: "PS5" },
  { id: "xbox", label: "Xbox" },
];

// Faster than the status bar: this screen is watched while someone is at the game's menu, waiting for the dot.
const POLL_MS = 1000;

/**
 * From opening the app to live packets, on PC or on a console over Wi-Fi.
 *
 * docs/design.md: no data yet is the normal first screen, not an error. It says what the app is doing,
 * what it waits for and the exact in-game values, with no red anywhere until something actually failed.
 */
export function SetupScreen() {
  useSetupPoll(POLL_MS);
  const setup = useSetup();

  if (!setup) {
    return (
      <Panel title="Setup">
        <p className="text-text-3">Waiting for the app&rsquo;s backend.</p>
      </Panel>
    );
  }
  return <SetupSteps setup={setup} />;
}

function SetupSteps({ setup }: { setup: SetupInfo }) {
  const [platform, setPlatform] = useState<Platform>(setup.listen_mode === "network" ? "ps5" : "pc");
  const [result, setResult] = useState<SettingsResult | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const onConsole = platform !== "pc";

  const save = async (change: SettingsChange) => {
    setSaving(true);
    setFailed(null);
    try {
      setResult(await saveSettings(change));
    } catch (error) {
      setResult(null);
      setFailed(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto grid max-w-[64rem] gap-[var(--f1-gap)]">
      <Panel title="1 · Where do you play?">
        <div className="flex gap-[var(--f1-space-2)]" role="radiogroup" aria-label="Platform">
          {PLATFORMS.map(({ id, label }) => (
            <Button
              key={id}
              role="radio"
              aria-checked={platform === id}
              variant={platform === id ? "default" : "outline"}
              onClick={() => setPlatform(id)}
            >
              {label}
            </Button>
          ))}
        </div>
      </Panel>

      <Panel title="2 · In the game">
        {onConsole && setup.listen_mode === "local" ? (
          <NetworkModeOff saving={saving} onEnable={() => void save({ listen_mode: "network" })} />
        ) : (
          <GameValues setup={setup} onConsole={onConsole} />
        )}
        {setup.listen_mode === "network" && <FirewallNote />}
        {result && !result.applied && (
          <p className="mt-[var(--f1-space-3)] text-critical">
            Couldn&rsquo;t listen with the new settings ({result.error}). They&rsquo;re saved, and the app is still
            listening on UDP {result.udp_port}. Restart the app to use them.
          </p>
        )}
        {failed && <p className="mt-[var(--f1-space-3)] text-critical">Couldn&rsquo;t save: {failed}</p>}
        <PortForm
          key={setup.udp_port}
          port={setup.udp_port}
          saving={saving}
          onSave={(port) => void save({ udp_port: port })}
        />
      </Panel>

      <Panel title="3 · Packet check">
        <PacketCheck setup={setup} />
      </Panel>
    </div>
  );
}

function GameValues({ setup, onConsole }: { setup: SetupInfo; onConsole: boolean }) {
  const address = onConsole ? setup.lan_addresses[0] : "127.0.0.1";
  const rows: [string, string, string?][] = [
    ["UDP Telemetry", "On"],
    ["UDP Broadcast Mode", "Off"],
    [
      "UDP IP Address",
      address ?? "—",
      onConsole && !address ? "No network address found. Is this PC on Wi-Fi or Ethernet?" : undefined,
    ],
    ["UDP Port", String(setup.udp_port)],
    ["UDP Send Rate", "60Hz", "20Hz works too; 60 is smoother."],
    ["UDP Format", "2026", "2025 works too, for F1 25 without the Season Pack."],
  ];
  return (
    <>
      <p className="mb-[var(--f1-space-3)] text-text-3">Settings → Telemetry Settings. Type these exactly:</p>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-[var(--f1-space-5)] gap-y-[var(--f1-space-2)]">
        {rows.map(([label, value, note]) => (
          <div key={label} className="contents">
            <dt className="text-text-3">{label}</dt>
            <dd>
              <span className="tnum font-semibold text-text-1">{value}</span>
              {note && <span className="ml-[var(--f1-space-3)] text-sm text-text-3">{note}</span>}
            </dd>
          </div>
        ))}
      </dl>
      {onConsole && setup.lan_addresses.length > 1 && (
        <p className="mt-[var(--f1-space-3)] text-sm text-text-3">
          Other addresses of this PC, if the first one doesn&rsquo;t work: {setup.lan_addresses.slice(1).join(", ")}
        </p>
      )}
    </>
  );
}

function NetworkModeOff({ saving, onEnable }: { saving: boolean; onEnable: () => void }) {
  return (
    <div className="flex flex-col items-start gap-[var(--f1-space-3)]">
      <p className="text-text-2">
        The app only listens to this PC right now. A console sends over your network, so the app has to listen there
        too.
      </p>
      <Button onClick={onEnable} disabled={saving}>
        Listen on the network
      </Button>
    </div>
  );
}

function FirewallNote() {
  return (
    <p className="mt-[var(--f1-space-4)] text-sm text-text-3">
      Windows may ask whether to let the app through the firewall. Allow it on <strong>private networks</strong>, or
      packets from the console never arrive. If you dismissed the prompt, allow it in Windows Security → Firewall &amp;
      network protection → Allow an app through firewall.
    </p>
  );
}

function PortForm({ port, saving, onSave }: { port: number; saving: boolean; onSave: (port: number) => void }) {
  const [value, setValue] = useState(String(port));
  const parsed = Number(value);
  const valid = Number.isInteger(parsed) && parsed >= 1024 && parsed <= 65535;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (valid && parsed !== port) onSave(parsed);
  };

  return (
    <form onSubmit={submit} className="mt-[var(--f1-space-4)] flex items-center gap-[var(--f1-space-2)] text-sm">
      <label htmlFor="udp-port" className="text-text-3">
        Another app already on this port? Change it:
      </label>
      <input
        id="udp-port"
        inputMode="numeric"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        className="tnum h-[var(--f1-control-h)] w-24 rounded-sm border border-border-control bg-surface-sunken px-2 text-text-1"
      />
      <Button type="submit" variant="outline" disabled={saving || !valid || parsed === port}>
        Apply
      </Button>
    </form>
  );
}

function PacketCheck({ setup }: { setup: SetupInfo }) {
  const status = useLiveStatus();
  const receiving = status === "live";
  return (
    <div className="flex flex-col gap-[var(--f1-space-2)]">
      <p className="flex items-center gap-[var(--f1-space-3)]">
        <span className={cn("size-3 rounded-full", receiving ? "bg-ok" : "bg-idle")} aria-hidden />
        <span className={receiving ? "text-text-1" : "text-text-2"}>
          {receiving
            ? `Receiving packets, UDP format ${setup.packet_format ?? "—"}`
            : status === "paused"
              ? "Packets stopped. The game is in a menu or the session ended."
              : `Listening on UDP ${setup.udp_port}. Waiting for the first packet.`}
        </span>
      </p>
      {setup.packet_warning && <p className="text-warn">{setup.packet_warning}</p>}
      {setup.packet_errors > 0 && (
        <p className="text-warn">
          {setup.packet_errors} packet{setup.packet_errors === 1 ? "" : "s"} couldn&rsquo;t be read. The app keeps
          listening; the log has the first error.
        </p>
      )}
    </div>
  );
}
