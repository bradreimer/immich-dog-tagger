interface Props {
  reason: string;
}

export function ReviewReason({ reason }: Props) {
  return (
    <div className="rounded-lg border p-3 text-sm text-muted-foreground">
      Review reason: {reason}
    </div>
  );
}