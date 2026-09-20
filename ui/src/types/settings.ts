export interface Settings {
  /** Base URL the backend uses to call the Immich API (`IMMICH_URL`). */
  immich_url: string;
  /**
   * Base URL for links the browser follows (`IMMICH_EXTERNAL_URL`, falling back
   * to `IMMICH_URL`). Differs from `immich_url` when the backend reaches Immich
   * over an internal network the reviewer's browser can't resolve.
   */
  immich_external_url: string;
  scanned_image_count: number;
  version: string;
  /**
   * How cautious automatic tagging is (issue #149). Unlike everything
   * above it this is owner-editable and lives in state.db, not the
   * environment.
   */
  tagging_sensitivity: TaggingSensitivity;
  /**
   * Configured Immich accounts (issue #346) -- always exactly one
   * ("default") for a legacy single-key deployment, so a single-entry list
   * here is not itself a signal anything changed.
   */
  accounts: Account[];
}

export interface Account {
  id: number;
  name: string;
}

export type TaggingSensitivity = "cautious" | "balanced" | "eager";
