import { IdentityChooser } from "./IdentityChooser";

interface Props {
  onCorrect: (identity: string) => void;
  onSkip: () => void;
  disabled?: boolean;
}

export function ReviewActions(props: Props) {
  return <IdentityChooser {...props} />;
}