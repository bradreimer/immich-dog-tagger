import { Separator } from "@/components/ui/separator";

export function KeyboardHints() {
  return (
    <div className="space-y-2 text-sm text-muted-foreground">
      <Separator />

      <p>
        Keyboard shortcuts:
      </p>

      <p>
        ← Previous
        {" · "}
        → Next
        {" · "}
        Space Accept
        {" · "}
        F Fibs
        {" · "}
        H Hermann
        {" · "}
        N Henri
        {" · "}
        U Unknown
      </p>
    </div>
  );
}