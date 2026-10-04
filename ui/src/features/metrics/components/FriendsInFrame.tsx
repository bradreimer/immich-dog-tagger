import { useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { FriendsInFrame as FriendsInFrameData } from "../../../types/metrics";
import { FriendsNetwork } from "./FriendsNetwork";
import { MostCommonPairs } from "./MostCommonPairs";

interface Props {
  data: FriendsInFrameData;
  onNavigate?: (path: string) => void;
}

/**
 * Metrics-tab section: which pets tend to appear together in the same photos.
 * A visualization of photo co-occurrence only -- not a claim about behavior.
 */
export function FriendsInFrame({ data, onNavigate }: Props) {
  const [highlightedPair, setHighlightedPair] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Friends in Frame</CardTitle>
        <CardDescription>Which animals tend to appear together in your photos?</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {data.nodes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No pets yet. Add a dog or cat and review a few photos to see who shows up together.
          </p>
        ) : (
          <>
            <FriendsNetwork
              nodes={data.nodes}
              edges={data.edges}
              highlightedEdgeKey={highlightedPair}
              onNavigate={onNavigate}
            />
            <MostCommonPairs nodes={data.nodes} edges={data.edges} onHoverPair={setHighlightedPair} onNavigate={onNavigate} />
          </>
        )}
      </CardContent>
    </Card>
  );
}
