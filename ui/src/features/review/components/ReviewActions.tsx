import { IdentityChooser } from "./IdentityChooser";

interface Props {
  onCorrect: (identity: string) => void;
  onSkip: () => void;
}

export function ReviewActions(props: Props) {
  return (
    <IdentityChooser {...props} />
  );
}