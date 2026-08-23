import { useCallback, useEffect, useState } from "react";

import { getSettings, setTaggingSensitivity } from "../../lib/api";
import type { Settings, TaggingSensitivity } from "../../types/settings";
import {
  IconCoffee,
  IconExternalLink,
  IconPhoto,
  IconRefresh,
  IconServer2,
  IconTag,
} from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatTile } from "@/components/ui/stat-tile";

const SENSITIVITIES: {
  value: TaggingSensitivity;
  label: string;
  description: string;
}[] = [
  {
    value: "cautious",
    label: "Ask me more often",
    description: "Tags fewer photos on its own and sends more for review.",
  },
  {
    value: "balanced",
    label: "Balanced",
    description: "The default.",
  },
  {
    value: "eager",
    label: "Tag more automatically",
    description: "Tags more photos on its own and sends fewer for review.",
  },
];

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      setSettings(await getSettings());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const changeSensitivity = useCallback(async (value: TaggingSensitivity) => {
    setSaving(true);
    setError(null);

    try {
      setSettings(await setTaggingSensitivity(value));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save setting");
    } finally {
      setSaving(false);
    }
  }, []);

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">
            Connection and scan coverage for this deployment.
          </p>
        </div>

        <Button variant="outline" onClick={() => load()} disabled={loading}>
          <IconRefresh className="h-4 w-4" aria-hidden="true" />
          Refresh
        </Button>
      </header>

      {error && (
        <Card>
          <CardHeader>
            <CardTitle>Settings Error</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => load()}>
              <IconRefresh className="h-4 w-4" aria-hidden="true" />
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {settings && (
        <Card>
          <CardHeader>
            <CardTitle>Immich Connection</CardTitle>
            <CardDescription>
              Configured via the <code>IMMICH_URL</code> and <code>IMMICH_EXTERNAL_URL</code>
              environment variables. Read-only here -- edit your deployment's environment to
              change them.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2">
              <StatTile
                icon={IconServer2}
                tone="info"
                label="Immich API URL"
                value={settings.immich_url || "Not configured"}
                subtext="used by the backend to reach Immich"
              />
              <StatTile
                icon={IconExternalLink}
                tone="info"
                label="Immich Link URL"
                value={settings.immich_external_url || "Not configured"}
                subtext="used by 'View in Immich' links in your browser"
              />
              <StatTile
                icon={IconPhoto}
                tone="accent"
                label="Images Scanned"
                value={settings.scanned_image_count}
                subtext="assets synced from Immich"
              />
            </div>
          </CardContent>
        </Card>
      )}

      {settings && (
        <Card>
          <CardHeader>
            <CardTitle>Automatic tagging</CardTitle>
            <CardDescription>
              How sure the app has to be before it tags a photo without asking
              you. Applies to the next pass — it never changes a photo you have
              already reviewed, and never rewrites past results on its own.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              className="flex flex-col gap-2"
              role="radiogroup"
              aria-label="Automatic tagging sensitivity"
            >
              {SENSITIVITIES.map((option) => {
                const selected = settings.tagging_sensitivity === option.value;

                return (
                  <button
                    key={option.value}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    disabled={saving}
                    onClick={() => changeSensitivity(option.value)}
                    className={`rounded-md border p-3 text-left transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                      selected
                        ? "border-primary bg-accent"
                        : "border-input hover:bg-accent/50"
                    }`}
                  >
                    <span className="block font-medium">{option.label}</span>
                    <span className="block text-sm text-muted-foreground">
                      {option.description}
                    </span>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {settings && (
        <Card>
          <CardHeader>
            <CardTitle>About</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <StatTile icon={IconTag} tone="neutral" label="Version" value={`v${settings.version}`} />
            </div>
            <a
              href="https://buymeacoffee.com/bradreimer"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            >
              <IconCoffee className="h-4 w-4" aria-hidden="true" />
              Buy Fibs and Hermann a treat
            </a>
          </CardContent>
        </Card>
      )}
    </section>
  );
}
