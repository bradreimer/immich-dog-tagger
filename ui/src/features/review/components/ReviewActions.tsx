import { IdentityChooser } from "./IdentityChooser";

interface Props {
  identities: string[];
  onCorrect: (identity: string) => void;
  onSkip: () => void;
  disabled?: boolean;
}

export function ReviewActions(props: Props) {
  return <IdentityChooser {...props} />;
}