import { useCallback, useEffect, useState } from "react";

import { getSettings } from "../../lib/api";
import type { Settings } from "../../types/settings";
import { IconPhoto, IconRefresh, IconServer2 } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatTile } from "@/components/ui/stat-tile";

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
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
              Configured via the <code>IMMICH_URL</code> environment variable. Read-only here --
              edit your deployment's environment to change it.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2">
              <StatTile
                icon={IconServer2}
                tone="info"
                label="Immich URL"
                value={settings.immich_url || "Not configured"}
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
    </section>
  );
}
